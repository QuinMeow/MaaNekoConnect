import json
from pathlib import Path

import numpy as np
import pytest
from maa.custom_recognition import CustomRecognition


ROOT = Path(__file__).resolve().parents[1]
REGIONS = {
    "donate_title": (250, 184, 221, 41), "coin": (462, 421, 28, 28),
    "price": (563, 419, 65, 32), "remaining": (550, 518, 68, 28),
    "donate_button": (501, 482, 75, 27), "button_red": (439, 474, 200, 82),
    "close": (310, 1135, 100, 100), "help_title": (269, 91, 185, 36),
    "help_batch": (212, 998, 296, 59), "help_none": (228, 655, 270, 32),
    "members_title": (45, 35, 170, 40), "greet_batch": (231, 1080, 259, 64),
    "guild_title": (45, 35, 170, 40), "footer_home": (280, 1195, 160, 75),
    "reward": (298, 398, 128, 32),
    "home_building": (535, 1105, 140, 110), "home_text": (530, 1205, 155, 65),
}


def test_guild_donation_is_opt_in_and_only_bounded_gold_is_executable(pipelines):
    interface = json.loads((ROOT / "assets/interface.json").read_text("utf-8"))
    assert interface["option"]["DailyGuildGoldDonation"]["default_case"] == "No"
    assert pipelines["DailyGuild_DonateSpend"]["max_hit"] == 10
    assert pipelines["DailyGuild_DonateSelect"]["enabled"] is False
    assert pipelines["DailyGuild_DonateSpend"]["on_error"] == ["Daily_StopCapture"]
    assert pipelines["DailyGuild_Start"]["anchor"]["CommonRecoveryResume"] == "DailyCore_Recover"


@pytest.mark.parametrize("sample", ["guild_donate10", "guild_donate9"])
def test_guild_donation_requires_gold_exact_price_positive_counter_and_button(native, frame, sample):
    if not all((ROOT / "assets/resource/model/ocr" / name).is_file()
               for name in ("det.onnx", "rec.onnx", "keys.txt")):
        pytest.skip("Native OCR models are not provisioned")
    image = frame("daily", sample, REGIONS)
    assert native.match("DailyGuild_DonateSpend", image)
    assert not native.match("DailyGuild_DonateSpend", (image * 0.75).astype(np.uint8))
    for key in ("donate_title", "coin", "price", "remaining", "donate_button", "close"):
        partial = image.copy()
        x, y, w, h = REGIONS[key]
        partial[y:y + h, x:x + w] = 0
        assert not native.match("DailyGuild_DonateSpend", partial), key


@pytest.mark.parametrize("quota,expected,stop", [(0, 0, False), (1, 1, False),
                                              (10, 10, False), (12, 10, True)])
def test_guild_gold_loop_rechecks_remaining_and_exhaustion_stops_without_reset(native, pipelines, quota, expected, stop):
    remaining, clicks = [quota], []

    class Quota(CustomRecognition):
        def analyze(self, context, argv):
            positive = json.loads(argv.custom_recognition_param)["positive"]
            return (0, 0, 1, 1) if (remaining[0] > 0) is positive else None

    assert native.resource.register_custom_recognition("GuildQuota", Quota())

    def click(x, y):
        assert remaining[0] > 0
        remaining[0] -= 1
        clicks.append((x, y))
        return True

    native.controller.on_click = click
    overrides = {name: {"post_delay": 0, "pre_delay": 0, "timeout": 20, "rate_limit": 1}
                 for name in pipelines}
    overrides["DailyGuild_Start"] = {**pipelines["DailyGuild_Start"], "next": ["DailyGuild_DonateDispatch"]}
    overrides["DailyGuild_DonateDispatch"].update(next=["DailyGuild_DonateGate", "DailyGuild_DonateZero"])
    overrides["DailyGuild_DonateSpend"].update(recognition="Custom", custom_recognition="GuildQuota",
                                               custom_recognition_param={"positive": True},
                                               next=["DailyGuild_DonateDispatch"])
    overrides["DailyGuild_DonateZero"] = {"recognition": "Custom", "custom_recognition": "GuildQuota",
                                          "custom_recognition_param": {"positive": False}, "next": ["GuildDone"]}
    overrides["GuildDone"] = {"recognition": "DirectHit", "post_delay": 0, "next": []}
    overrides["Daily_StopCapture"]["action"] = "DoNothing"
    names = [node.name for node in native.run("DailyGuild_Start", overrides).nodes]
    assert len(clicks) == expected and names[-1] == ("Daily_Stop" if stop else "GuildDone")


@pytest.mark.parametrize("confirmed", [False, True])
def test_donation_requires_exactly_one_counter_decrease_before_another_action(native, pipelines, confirmed):
    class Never(CustomRecognition):
        def analyze(self, context, argv):
            return None

    assert native.resource.register_custom_recognition("GuildNever", Never())
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    overrides = {name: {"post_delay": 0, "pre_delay": 0, "timeout": 20, "rate_limit": 1}
                 for name in pipelines}
    overrides["DailyGuild_Start"] = {**pipelines["DailyGuild_Start"], "next": ["DailyGuild_DonateQuota2"]}
    for name in ("DailyGuild_DonateQuota2", "DailyGuild_DonateGate", "DailyGuild_DonateSpend"):
        overrides[name]["recognition"] = "DirectHit"
    overrides["DailyGuild_DonateSeen1"].update(recognition="DirectHit" if confirmed else "Custom",
                                              custom_recognition="GuildNever", next=["GuildDone"])
    overrides["GuildDone"] = {"recognition": "DirectHit", "post_delay": 0, "next": []}
    overrides["Daily_StopCapture"]["action"] = "DoNothing"
    names = [node.name for node in native.run("DailyGuild_Start", overrides).nodes]
    assert len(clicks) == 1 and names[-1] == ("GuildDone" if confirmed else "Daily_Stop")


@pytest.mark.parametrize("sample,node", [("guild_help", "DailyGuild_HelpBatch"),
                                        ("guild_no_help", "DailyGuild_NoHelp"),
                                        ("guild_members", "DailyGuild_GreetBatch"),
                                        ("guild_reward", "DailyGuild_RewardClose")])
def test_guild_help_greet_and_rewards_match_only_their_observed_controls(native, frame, sample, node):
    if sample != "guild_reward" and not (ROOT / "assets/resource/model/ocr/rec.onnx").is_file():
        pytest.skip("Native OCR models are not provisioned")
    image = frame("daily", sample, REGIONS)
    assert native.match(node, image)
    assert not native.match(node, np.zeros_like(image))


@pytest.mark.parametrize("gate,action", [("DailyGuild_HelpGate", "DailyGuild_HelpBatch"),
                                       ("DailyGuild_GreetGate", "DailyGuild_GreetBatch")])
def test_guild_help_and_greet_are_not_repeated_when_controls_persist(native, gate, action):
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    overrides = {
        gate: {"recognition": "DirectHit", "post_delay": 0, "timeout": 20},
        action: {"recognition": "DirectHit", "action": "Click", "target": [350, 1000],
                 "post_delay": 0, "next": [gate]},
        "Daily_StopCapture": {"action": "DoNothing", "post_delay": 0},
        "Daily_Stop": {"post_delay": 0},
    }
    names = [node.name for node in native.run(gate, overrides).nodes]
    assert len(clicks) == 1 and names[-1] == "Daily_Stop"


def test_guild_default_flow_helps_greets_and_returns_without_donation(native, pipelines, frame):
    if not (ROOT / "assets/resource/model/ocr/rec.onnx").is_file():
        pytest.skip("Native OCR models are not provisioned")
    images = [frame("daily", sample, REGIONS) for sample in
              ("guild_help", "guild_no_help", "guild_ready", "guild_members", "guild_reward", "guild_members")]
    images.append(frame("recovery", "home_ready_holdout", REGIONS))
    assert native.match("DailyGuild_Page", images[2])
    native.controller.image = images[0]
    clicks = []

    def click(x, y):
        clicks.append((x, y))
        native.controller.image = images[len(clicks)]
        return True

    native.controller.on_click = click
    overrides = {name: {"post_delay": 0, "pre_delay": 0, "timeout": 30, "rate_limit": 1}
                 for name in pipelines}
    overrides["DailyGuild_Start"] = {**pipelines["DailyGuild_Start"], "next": ["DailyGuild_HelpDispatch"]}
    names = [node.name for node in native.run("DailyGuild_Start", overrides).nodes]
    assert len(clicks) == 6 and names[-1] == "DailyCore_Done"
    assert names.count("DailyGuild_HelpBatch") == names.count("DailyGuild_GreetBatch") == 1
    assert "DailyGuild_DonateSpend" not in names


@pytest.mark.parametrize("sample,node,other", [
    ("guild_ready_holdout", "DailyGuild_Page", "DailyGuild_MembersPage"),
    ("guild_members_full", "DailyGuild_MembersPage", "DailyGuild_Page"),
])
def test_full_title_survives_repeated_native_page_and_gate_action_checks(native, pipelines, frame, sample, node, other):
    image = frame("daily", sample, {"title": (0, 20, 300, 80), "footer": (280, 1195, 160, 75)})
    hits = [native.match(node, image) for _ in range(2)]
    assert hits == [True, True], hits
    assert not native.match(other, image)
    for x, y, w, h in ((0, 20, 300, 80), (280, 1195, 160, 75)):
        missing = image.copy()
        missing[y:y + h, x:x + w] = 0
        assert not native.match(node, missing)
    native.controller.image = image
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    patch = {name: {"pre_delay": 0, "post_delay": 0, "timeout": 40, "rate_limit": 1} for name in pipelines}
    patch["NavHome_FromKnownBusiness"]["next"] = []
    patch["CommonRecoveryStopCapture"]["action"] = "DoNothing"
    names = [value.name for value in native.run("NavHome_KnownBusinessGate", patch).nodes]
    assert names[-1] == "NavHome_FromKnownBusiness" and len(clicks) == 1, names
