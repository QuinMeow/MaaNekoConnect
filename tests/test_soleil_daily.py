import json
from types import SimpleNamespace

import numpy as np
import pytest

from maa.context import ContextEventSink

from agent.soleil import SoleilBathArrow


REGIONS = {"title": (0, 20, 160, 70), "footer": (85, 1195, 540, 75),
           "selected": (610, 1085, 90, 60), "small_label": (245, 410, 155, 40),
           "small_bath": (250, 498, 235, 120), "big_label": (155, 220, 270, 58),
           "big_bath": (330, 390, 65, 65), "side": (610, 735, 80, 90),
           "enhance": (610, 420, 85, 90), "clipped_label": (30, 0, 440, 40),
           "clipped_bath": (325, 235, 70, 80), "floor": (30, 130, 170, 45),
           "kitchen": (30, 310, 170, 45), "waiting": (30, 490, 150, 45),
           "bath_title": (30, 760, 150, 45), "auto": (230, 1080, 260, 70),
           "ducks": (470, 25, 170, 50)}
BOXES = [[345, 400, 28, 34], [435, 460, 28, 34]]


def result(items=()):
    return SimpleNamespace(hit=bool(items), filtered_results=list(items), all_results=list(items),
                           best_result=items[0] if items else None)


def context(quota=2, boxes=BOXES):
    state = {"baseline": None, "history": [], "pending": None, "duck_rewards": []}
    ctx = SimpleNamespace(tasker=SimpleNamespace(stopping=False), quota=quota, boxes=boxes,
                          page=True, ducks=3, duck_score=1.0, fail=None, logs=[])
    ctx.get_node_data = lambda name: {"custom_recognition_param": json.loads(json.dumps(state))}

    def override(patch):
        if ctx.fail in patch:
            return False
        if "Soleil_BathState" in patch:
            state.update(patch["Soleil_BathState"]["custom_recognition_param"])
        if "Soleil_BathLog" in patch:
            ctx.logs.append(patch["Soleil_BathLog"]["focus"]["Node.Action.Succeeded"])
        return True

    def recognize(name, image, override=None):
        if name in ("Soleil_BathPage", "Soleil_BathDuckIcon"):
            return result([SimpleNamespace(score=1.0)]) if ctx.page else result()
        if name == "Soleil_BathQuotaLabel":
            return result([SimpleNamespace(box=[180, 235, 140, 29], score=1.0)])
        if name in ("Soleil_BathQuota", "Soleil_BathDuckCount"):
            value, score = (ctx.quota, 1.0) if name.endswith("Quota") else (ctx.ducks, ctx.duck_score)
            return result([SimpleNamespace(text=str(value), score=score)])
        assert name == "Soleil_BathMarkers"
        return result([SimpleNamespace(box=box, score=1.0) for box in ctx.boxes])

    ctx.override_pipeline, ctx.run_recognition = override, recognize
    return ctx, state


def argv(op="target"):
    return SimpleNamespace(image=np.zeros((1280, 720, 3), dtype=np.uint8), roi=[150, 180, 450, 470],
                           custom_recognition_param=json.dumps({"op": op}))


def initialized(quota=2, boxes=BOXES):
    ctx, state = context(quota, boxes)
    reco = SoleilBathArrow()
    assert reco.analyze(ctx, argv("reset")) is not None
    return reco, ctx, state


def test_each_confirmed_collection_logs_its_own_one_to_ten_duck_delta():
    reco, ctx, state = initialized()
    ctx.ducks = 0
    for index, balance in enumerate((1, 11)):
        assert reco.analyze(ctx, argv()) is not None
        assert state["pending"]["ducks_before"] == (0 if index == 0 else 1)
        ctx.quota, ctx.boxes, ctx.ducks = 1 - index, BOXES[index + 1:], balance
        assert reco.analyze(ctx, argv()) is None
        assert reco.analyze(ctx, argv("confirm")) is not None
        assert state["duck_rewards"] == [1, 10][:index + 1]
        assert f"+{(1, 10)[index]}" in ctx.logs[-1] and "鸭子" in ctx.logs[-1]
    assert reco.analyze(ctx, argv("done")) is not None
    assert reco.analyze(ctx, argv("reset")) is None and len(state["history"]) == 2


@pytest.mark.parametrize("after,score", [(3, 1.0), (2, 1.0), (14, 1.0), (None, 1.0), (6, 0.5)])
def test_unknown_delta_never_becomes_zero_or_replays_a_confirmed_collection(after, score):
    reco, ctx, state = initialized(1, BOXES[:1])
    assert reco.analyze(ctx, argv()) is not None
    ctx.quota, ctx.boxes, ctx.ducks, ctx.duck_score = 0, [], after, score
    assert reco.analyze(ctx, argv("confirm")) is None
    assert reco.analyze(ctx, argv("confirm_unknown")) is not None
    assert state["duck_rewards"] == [None] and state["pending"] is None
    assert "未确认" in ctx.logs[-1] and "+0" not in ctx.logs[-1]
    assert reco.analyze(ctx, argv("done")) is not None


@pytest.mark.parametrize("quota,boxes", [(2, []), (0, []), (1, BOXES), (2, BOXES[1:])])
def test_unconfirmed_click_never_authorizes_another_target_or_done(quota, boxes):
    reco, ctx, state = initialized()
    assert reco.analyze(ctx, argv()) is not None
    ctx.quota, ctx.boxes, ctx.ducks = quota, boxes, 6
    for op in ("target", "done", "confirm", "confirm_unknown"):
        assert reco.analyze(ctx, argv(op)) is None
    assert state["pending"]["quota"] == 2 and state["duck_rewards"] == [] and not ctx.logs


@pytest.mark.parametrize("quota", [0, 1])
def test_empty_bath_never_fabricates_rewards_or_resets_a_live_budget(quota):
    reco, ctx, state = initialized(quota, [])
    assert (reco.analyze(ctx, argv("done")) is not None) is (quota == 0)
    assert reco.analyze(ctx, argv()) is None and reco.analyze(ctx, argv("reset")) is None
    assert state["history"] == state["duck_rewards"] == [] and not ctx.logs


@pytest.mark.parametrize("invalid", ["unknown", "cancelled", "state", "write", "side", "log"])
def test_unknown_cancelled_invalid_state_or_failed_writes_cannot_authorize_click(invalid):
    reco, ctx, state = initialized()
    if invalid == "unknown":
        ctx.page = False
    elif invalid == "cancelled":
        ctx.tasker.stopping = True
    elif invalid == "state":
        state["history"] = [[1, 2]]
    elif invalid == "side":
        ctx.boxes = [[640, 740, 28, 34]]
    else:
        assert reco.analyze(ctx, argv()) is not None
        ctx.quota, ctx.boxes, ctx.ducks = 1, BOXES[1:], 6
        ctx.fail = "Soleil_BathLog" if invalid == "log" else "Soleil_BathState"
        assert reco.analyze(ctx, argv("confirm")) is None
    assert reco.analyze(ctx, argv()) is None


@pytest.mark.parametrize("case", ["sequence", "persistent", "zero"])
def test_native_sequence_logs_real_duck_deltas_before_any_next_click(native, frame, pipelines, case):
    images = [frame("soleil_daily", sample, REGIONS)
              for sample in ("bath_small_two", "bath_zoom_one", "bath_small_zero", "bath_zoom_zero")]
    native.controller.image = images[-1] if case == "zero" else images[0]
    clicks, messages = [], []

    class Logs(ContextEventSink):
        def on_raw_notification(self, context, message, details):
            if message == "Node.Action.Succeeded" and details["name"] == "Soleil_BathLog":
                messages.append(details["focus"]["Node.Action.Succeeded"])

    native.tasker.add_context_sink(Logs())

    def click(x, y):
        if case == "sequence":
            assert len(messages) == len(clicks)
        clicks.append((x, y))
        if case != "persistent":
            native.controller.image = images[min(len(clicks), 2)]
        return True

    native.controller.on_click = click
    patch = {name: {"pre_delay": 0, "post_delay": 0, "timeout": 30, "rate_limit": 1}
             for name in pipelines}
    names = [node.name for node in native.run("Soleil_BathInit", patch).nodes]
    assert names[-1] == ("CommonRecoveryStop" if case == "persistent" else "Soleil_BathComplete")
    assert len(clicks) == {"sequence": 2, "persistent": 2, "zero": 0}[case]
    assert ("Soleil_BathUnconfirmed" in names) is (case == "persistent")
    assert ("Soleil_BathDone" in names) is (case != "persistent")
    assert len(set(clicks)) == len(clicks)
    if case == "sequence":
        assert names.count("Soleil_BathLog") == 2
        assert all(f"+{delta}" in message for delta, message in zip((3, 1), messages))


@pytest.mark.parametrize("sample", ["bath_clipped_one", "bath_clipped_zero"])
def test_clipped_quota_never_means_zero_or_authorizes_collection(native, frame, sample):
    image = frame("soleil_daily", sample, REGIONS)
    for node in ("Soleil_BathPage", "Soleil_BathInit", "Soleil_BathCollect", "Soleil_BathDone"):
        assert not native.match(node, image)


@pytest.mark.parametrize("page,entry,terminal", [
    ("bath_small_two", "TestSoleilReturn", "DailyCore_Done"), ("duty", "TestSoleilReturn", "DailyCore_Done"),
    ("bath_small_two", "Soleil_BathUnconfirmed", "Soleil_Stop"), ("duty", "Soleil_DutyUnconfirmed", "Soleil_Stop"),
])
def test_safe_home_return_does_not_resume_unconfirmed_soleil_work(native, frame, pipelines, page, entry, terminal):
    clicks = []
    home = frame("navigation", "home_ready", {"home_building": (535, 1105, 140, 110),
                 "home_label": (530, 1205, 155, 65)})
    native.controller.image = frame("soleil_daily", page, REGIONS)
    def click(x, y):
        clicks.append((x, y))
        native.controller.image = home
        return True

    native.controller.on_click = click
    patch = {name: {"post_delay": 0, "timeout": 100, "rate_limit": 1} for name in pipelines}
    patch["TestSoleilReturn"] = {"recognition": "DirectHit", "post_delay": 0,
        "anchor": {"NavHome_Return": "DailyCore_Done"}, "next": ["NavHome_Ensure"]}
    names = [node.name for node in native.run(entry, patch).nodes]
    assert names[-1] == terminal and len(clicks) == 1
    assert 280 <= clicks[0][0] <= 440 and 1195 <= clicks[0][1] <= 1270
    assert "Soleil_BathCollect" not in names and "Soleil_DutyChange" not in names
    assert not {"Soleil_BathComplete", "Soleil_DutyComplete", "Soleil_Done"}.intersection(names)
