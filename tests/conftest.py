import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tools"), str(ROOT / "agent")]
SOLEIL_REGIONS = {
    "title": (0, 20, 160, 70), "furniture": (30, 1088, 215, 55),
    "level": (495, 865, 80, 55), "ascending": (645, 867, 52, 52),
    "list_top": (685, 433, 16, 39), "button": (230, 998, 260, 70),
    "first_row": (30, 433, 650, 140), "home_building": (535, 1105, 140, 110),
    "home_text": (530, 1205, 155, 65), "filter_dialog": (85, 180, 550, 640),
    "filter_tabs": (50, 835, 620, 50), "apply": (440, 900, 160, 65),
    "open_enhance": (610, 420, 85, 90), "request": (610, 630, 85, 90),
    "busy_marker1": (65, 460, 70, 65), "selected_border1": (37, 470, 3, 40),
    "timer": (520, 1000, 125, 65),
}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def reject(*args, **kwargs):
        pytest.fail("Offline tests must not start processes or connect to devices/network")

    for name in ("subprocess.run", "subprocess.Popen", "socket.create_connection", "socket.socket.connect"):
        monkeypatch.setattr(name, reject)


@pytest.fixture
def pipelines():
    nodes = {}
    for path in (ROOT / "assets/resource/pipeline").glob("*.json"):
        for name, node in json.loads(path.read_text("utf-8")).items():
            assert name not in nodes, name
            nodes[name] = node
    return nodes


@pytest.fixture
def frame():
    def load(group, sample, regions):
        image = np.zeros((1280, 720, 3), dtype=np.uint8)
        with np.load(ROOT / "tests/fixtures" / group / f"{sample}.npz", allow_pickle=False) as crops:
            assert crops.files and set(crops.files) <= regions.keys()
            for name in crops.files:
                x, y, width, height = regions[name]
                assert crops[name].shape == (height, width, 3) and crops[name].dtype == np.uint8
                image[y:y + height, x:x + width] = crops[name]
        return image
    return load


@pytest.fixture
def soleil_image(frame):
    return lambda sample: frame("soleil", sample, SOLEIL_REGIONS)


@pytest.fixture
def native(tmp_path):
    from maa.controller import CustomController
    from maa.define import LoggingLevelEnum
    from maa.pipeline import JAnd
    from maa.resource import Resource
    from maa.tasker import Tasker

    class Controller(CustomController):
        def __init__(self):
            self.image = np.zeros((1280, 720, 3), dtype=np.uint8)
            self.source = None
            self.on_click = self.on_start = self.on_stop = None
            self.rejected = []
            super().__init__()

        def connect(self):
            return True

        def request_uuid(self):
            return "offline-tests"

        def get_features(self):
            return 0

        def screencap(self):
            return self.source() if self.source else self.image.copy()

        def click(self, x, y):
            return self.on_click(x, y) if self.on_click else self.reject(x, y)

        def start_app(self, package):
            return self.on_start(package) if self.on_start else self.reject(package)

        def stop_app(self, package):
            return self.on_stop(package) if self.on_stop else self.reject(package)

        def reject(self, *args):
            self.rejected.append(args)
            return False

        swipe = touch_down = touch_move = touch_up = reject
        click_key = input_text = key_down = key_up = scroll = relative_move = reject

        def shell(self, *args):
            self.reject(*args)
            return None

    Tasker.set_log_dir(tmp_path / "native-logs")
    Tasker.set_stdout_level(LoggingLevelEnum.Off)
    Tasker.set_save_draw(False)
    Tasker.set_save_on_error(False)
    controller, resource, tasker = Controller(), Resource(), Tasker()
    assert controller.post_connection().wait().succeeded
    assert resource.post_bundle(ROOT / "assets/resource").wait().succeeded
    assert tasker.bind(resource, controller)

    def finish(job):
        deadline = time.monotonic() + 5
        while not job.done and time.monotonic() < deadline:
            time.sleep(0.005)
        assert job.done, "Offline native job exceeded five seconds"
        assert job.succeeded
        detail = job.get()
        assert detail is not None
        return detail

    def match(name, image):
        detail = finish(tasker.post_recognition("And", JAnd(all_of=[name]), image))
        assert len(detail.nodes) == 1 and detail.nodes[0].action is None
        return detail.nodes[0].recognition.hit

    yield SimpleNamespace(controller=controller, resource=resource, tasker=tasker, match=match,
                          run=lambda entry, overrides: finish(tasker.post_task(entry, overrides)))
    tasker.post_stop().wait()
    assert not controller.rejected, controller.rejected
