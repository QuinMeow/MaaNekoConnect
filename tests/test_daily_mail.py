from pathlib import Path

import numpy as np
import pytest


REGIONS = {
    "mail_title": (180, 80, 360, 70), "mail_batch": (250, 934, 218, 43),
    "mail_tab": (55, 1018, 230, 44), "close": (310, 1135, 100, 100),
    "reward": (298, 398, 128, 32), "capacity_header": (88, 201, 154, 22),
    "capacity_footer": (210, 919, 310, 30),
    "home_building": (535, 1105, 140, 110), "home_text": (530, 1205, 155, 65),
}


def require_ocr():
    model = Path(__file__).resolve().parents[1] / "assets/resource/model/ocr"
    if not all((model / name).is_file() for name in ("det.onnx", "rec.onnx", "keys.txt")):
        pytest.skip("Native OCR models are not provisioned")


def test_mail_collects_once_and_never_restarts_after_capacity_rejection(pipelines):
    assert pipelines["DailyMail_Collect"]["max_hit"] == 1
    assert pipelines["DailyMail_ClosePermit"]["max_hit"] == 3
    assert pipelines["DailyMail_Collect"]["on_error"] == ["Daily_StopCapture"]
    assert pipelines["DailyMail_Start"]["anchor"]["CommonRecoveryResume"] == "DailyCore_Recover"


@pytest.mark.parametrize("sample,node,required", [
    ("mail_ready", "DailyMail_Collect", ("mail_title", "mail_batch", "mail_tab", "close")),
    ("mail_capacity", "DailyMail_CapacityClose", ("capacity_header", "capacity_footer", "close")),
    ("mail_reward", "DailyMail_RewardClose", ("reward", "close")),
])
def test_mail_controls_require_the_specific_complete_unobscured_page(native, frame, sample, node, required):
    if sample == "mail_ready":
        require_ocr()
    image = frame("daily", sample, REGIONS)
    assert native.match(node, image)
    for key in required:
        partial = image.copy()
        x, y, w, h = REGIONS[key]
        partial[y:y + h, x:x + w] = 0
        assert not native.match(node, partial), key
    assert not native.match(node, np.zeros_like(image))
    if sample != "mail_ready":
        assert not native.match("DailyMail_Collect", image)


def test_mail_reward_capacity_and_remaining_items_return_home_without_another_batch(native, pipelines, frame):
    require_ocr()
    images = [frame("daily", sample, REGIONS) for sample in
              ("mail_ready", "mail_reward", "mail_capacity", "mail_remaining")]
    images.append(frame("recovery", "home_ready_holdout", REGIONS))
    native.controller.image = images[0]
    clicks = []

    def click(x, y):
        clicks.append((x, y))
        native.controller.image = images[len(clicks)]
        return True

    native.controller.on_click = click
    overrides = {name: {"post_delay": 0, "pre_delay": 0, "timeout": 30, "rate_limit": 1}
                 for name in pipelines}
    overrides["DailyMail_Start"] = {**pipelines["DailyMail_Start"],
                                    "next": ["DailyMail_Dispatch"], "post_delay": 0}
    names = [node.name for node in native.run("DailyMail_Start", overrides).nodes]
    assert len(clicks) == 4 and names[-1] == "DailyCore_Done", names
    assert names.count("DailyMail_Collect") == 1 and names.count("DailyMail_ClosePermit") == 3
    assert "DailyMail_CapacityClose" in names
    assert not any(name.endswith("Spend") or name in ("Daily_Claim", "Daily_MilestoneClaim") for name in names)


def test_persistent_mail_capacity_popup_exhausts_close_budget_without_retrying_collection(native, pipelines, frame):
    native.controller.image = frame("daily", "mail_capacity", REGIONS)
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    overrides = {name: {"post_delay": 0, "pre_delay": 0, "timeout": 30, "rate_limit": 1}
                 for name in pipelines}
    overrides["DailyMail_Start"] = {**pipelines["DailyMail_Start"],
                                    "next": ["DailyMail_AfterCollect"], "post_delay": 0}
    overrides["Daily_StopCapture"]["action"] = "DoNothing"
    names = [node.name for node in native.run("DailyMail_Start", overrides).nodes]
    assert len(clicks) == 3 and names[-1] == "Daily_Stop"
    assert "DailyMail_Collect" not in names
