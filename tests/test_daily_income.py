from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]


def home():
    image = np.zeros((1280, 720, 3), dtype=np.uint8)
    with np.load(ROOT / "tests/fixtures/recovery/home_ready_holdout.npz") as crops:
        for key, (x, y) in {"home_building": (535, 1105), "home_text": (530, 1205)}.items():
            crop = crops[key]
            image[y:y + crop.shape[0], x:x + crop.shape[1]] = crop
    return image


@pytest.mark.parametrize("icon", [0, 120, 255])
def test_income_entry_does_not_depend_on_the_accumulated_income_icon(native, icon):
    image = home()
    image[1025:1110, 430:505] = icon
    assert native.match("Daily_IncomeBegin", image)
    assert not native.match("Daily_IncomeClaim", image), "Opening is not permission to claim blindly"
    assert not native.match("Daily_IncomeBegin", (image * 0.6).astype(np.uint8))


def test_unrecognized_income_dialog_never_repeats_open_or_claim(native, pipelines):
    native.controller.image = home()
    clicks = []

    def open_dialog(x, y):
        clicks.append((x, y))
        native.controller.image[:] = 0
        return True

    native.controller.on_click = open_dialog
    patch = {name: {"pre_delay": 0, "post_delay": 0, "timeout": 30, "rate_limit": 1}
             for name in pipelines}
    patch["Daily_IncomeBegin"]["on_error"] = ["Daily_StopCapture"]
    patch["Daily_StopCapture"]["action"] = "DoNothing"
    names = [node.name for node in native.run("Daily_IncomeBegin", patch).nodes]
    assert len(clicks) == 1 and names[-1] == "Daily_Stop"
    assert "Daily_IncomeClaim" not in names
