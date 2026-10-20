import json
from types import SimpleNamespace

import numpy as np
import pytest

from agent import ad_close


def test_provider_is_off_without_explicit_consent():
    assert ad_close.load_config({}) is None
    assert ad_close.load_config({"MAANEKO_AD_LLM_ENDPOINT": "https://example.test"}) is None
    with pytest.raises(ValueError):
        ad_close.load_config({"MAANEKO_AD_LLM_ENABLED": "1"})


@pytest.mark.parametrize("endpoint", [
    "http://example.test/v1/chat/completions", "https://u:p@example.test/v1/chat/completions",
    "https://example.test/v1/chat/completions?key=secret", "file:///chat/completions",
])
def test_provider_rejects_insecure_or_ambiguous_destination(endpoint):
    with pytest.raises(ValueError):
        ad_close.load_config({"MAANEKO_AD_LLM_ENABLED": "1", "MAANEKO_AD_LLM_ENDPOINT": endpoint,
                              "MAANEKO_AD_LLM_MODEL": "vision", "MAANEKO_AD_LLM_API_KEY": "secret"})


def close(**changes):
    value = {"action": "close", "region": "top_right", "box": [70, 20, 24, 24],
             "label": "X", "confidence": 0.99}
    return value | changes


def test_only_high_confidence_small_close_targets_in_corners_are_allowed():
    assert ad_close.validate_decision(close()) == (674, 32)
    assert ad_close.validate_decision({"action": "wait"}) is None
    assert ad_close.validate_decision({"action": "unknown"}) is None
    for value in (close(action="buy"), close(region="center"), close(box=[70, 20, 80, 24]),
                  close(label="Install"), close(label="Close and buy"), close(confidence=0.97),
                  close(confidence=float("nan")), close(box=[True, 20, 24, 24]),
                  close(url="https://example.test"), {"action": "wait", "x": 10}):
        with pytest.raises(ValueError):
            ad_close.validate_decision(value)


def test_upload_contains_only_corners_not_center_or_game_account():
    image = np.zeros((1280, 720, 3), dtype=np.uint8)
    image[200:1080, 128:592] = 255
    montage = ad_close.corner_montage(image)
    assert montage.shape == (128, 512, 3) and not montage.any()
    assert ad_close.encode_png(montage).startswith(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(ValueError):
        ad_close.corner_montage(np.zeros((720, 1280, 3), dtype=np.uint8))


class Context:
    def __init__(self):
        self.state = {"custom_action_param": {"frames": 0, "calls": 0, "clicks": 0}}
        self.clicks = []
        self.native_box = None
        self.tasker = SimpleNamespace(stopping=False)
        self.tasker.controller = SimpleNamespace(
            cached_image=np.zeros((1280, 720, 3), dtype=np.uint8),
            post_screencap=lambda: SimpleNamespace(wait=lambda: SimpleNamespace(succeeded=True)),
            post_click=lambda x, y: self.click(x, y),
        )

    def click(self, x, y):
        self.clicks.append((x, y))
        return SimpleNamespace(wait=lambda: SimpleNamespace(succeeded=True))

    def get_node_data(self, name):
        return self.state

    def override_pipeline(self, updates):
        self.state = next(iter(updates.values()))
        return True

    def run_recognition(self, name, image):
        return SimpleNamespace(hit=True, box=self.native_box) if self.native_box else None


def invoke(context):
    return ad_close.AdCloseControl().run(context, SimpleNamespace(custom_action_param="{}"))


def test_unconfigured_waits_bounded_without_upload_or_click(monkeypatch):
    monkeypatch.setattr(ad_close.os, "environ", {})
    monkeypatch.setattr(ad_close, "request_decision", lambda *_: pytest.fail("Unexpected upload"))
    context = Context()
    assert all(invoke(context) for _ in range(40))
    assert not invoke(context) and not context.clicks


def test_native_close_precedes_model_and_click_budget_is_committed(monkeypatch):
    monkeypatch.setattr(ad_close.os, "environ", {})
    monkeypatch.setattr(ad_close, "request_decision", lambda *_: pytest.fail("Unexpected upload"))
    context = Context()
    context.native_box = [662, 24, 24, 24]
    assert all(invoke(context) for _ in range(3))
    assert not invoke(context) and len(context.clicks) == 3
    context.tasker.stopping = True
    assert not invoke(context)


def test_failed_click_is_never_replayed_by_new_state_initialization(monkeypatch):
    monkeypatch.setattr(ad_close.os, "environ", {})
    context = Context()
    context.native_box = [662, 24, 24, 24]
    context.tasker.controller.post_click = lambda *_: SimpleNamespace(
        wait=lambda: SimpleNamespace(succeeded=False))
    assert not invoke(context)
    saved = context.state["custom_action_param"]
    assert saved["clicks"] == 1 and saved["frames"] == 1
    assert not ad_close.AdCloseControl().run(context, SimpleNamespace(custom_action_param='{"reset": true}'))


def test_provider_budget_and_cropped_request_are_bounded(monkeypatch):
    env = {"MAANEKO_AD_LLM_ENABLED": "1", "MAANEKO_AD_LLM_ENDPOINT":
           "https://example.test/v1/chat/completions", "MAANEKO_AD_LLM_MODEL": "vision",
           "MAANEKO_AD_LLM_API_KEY": "secret"}
    monkeypatch.setattr(ad_close.os, "environ", env)
    requests = []
    monkeypatch.setattr(ad_close, "request_decision", lambda image, config:
                        requests.append(image.shape) or {"action": "wait"})
    context = Context()
    assert all(invoke(context) for _ in range(40))
    assert len(requests) == 4 and set(requests) == {(128, 512, 3)}
    assert not invoke(context) and not context.clicks


def test_stale_model_screenshot_cannot_authorize_click(monkeypatch):
    monkeypatch.setattr(ad_close.os, "environ", {"MAANEKO_AD_LLM_ENABLED": "1",
                        "MAANEKO_AD_LLM_ENDPOINT": "https://example.test/v1/chat/completions",
                        "MAANEKO_AD_LLM_MODEL": "vision", "MAANEKO_AD_LLM_API_KEY": "secret"})
    context = Context()

    def changed(*_):
        context.tasker.controller.cached_image[0:128, 592:720] = 255
        return close()

    monkeypatch.setattr(ad_close, "request_decision", changed)
    assert all(invoke(context) for _ in range(14))
    assert not context.clicks


def test_provider_uses_explicit_destination_without_redirect_or_proxy(monkeypatch):
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read1(self, size):
            seen["limit"] = size
            if seen.get("read"):
                return b""
            seen["read"] = True
            return b'{"choices":[{"message":{"content":"{\\"action\\":\\"wait\\"}"}}]}'

    def open_request(request, timeout):
        seen.update(url=request.full_url, timeout=timeout, body=json.loads(request.data))
        return Response()

    def build(*handlers):
        assert handlers[0].proxies == {} and isinstance(handlers[1], ad_close._NoRedirect)
        return SimpleNamespace(open=open_request)

    monkeypatch.setattr(ad_close.urllib.request, "build_opener", build)
    config = {"endpoint": "https://example.test/v1/chat/completions", "model": "vision", "api_key": "secret"}
    assert ad_close.request_decision(np.zeros((128, 512, 3), dtype=np.uint8), config) == {"action": "wait"}
    assert seen["url"] == config["endpoint"] and seen["limit"] == 4096 and seen["timeout"] == 8
    assert seen["body"]["max_tokens"] == 160
    with pytest.raises(ValueError):
        ad_close._NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.test")
    with pytest.raises(ValueError):
        ad_close._read_response(SimpleNamespace(read1=lambda _: b"x" * 65537), float("inf"))
    clock = iter([0, 5, 10])
    monkeypatch.setattr(ad_close.time, "monotonic", lambda: next(clock))
    with pytest.raises(TimeoutError):
        ad_close._read_response(SimpleNamespace(read1=lambda _: b"x"), 8)


def test_normalized_native_state_cannot_reset_advertisement_limits(monkeypatch):
    monkeypatch.setattr(ad_close.os, "environ", {})
    context = Context()
    context.state = {"action": {"type": "Custom", "param": {
        "custom_action_param": {"frames": 40, "calls": 4, "clicks": 0}}}}
    assert not invoke(context) and not context.clicks


@pytest.mark.parametrize("state", [None, {}, {"custom_action_param": {"frames": 0}}])
def test_missing_budget_never_renews_advertisement_permits(state, monkeypatch):
    monkeypatch.setattr(ad_close.os, "environ", {})
    context = Context()
    context.state = state
    assert not invoke(context) and not context.clicks
