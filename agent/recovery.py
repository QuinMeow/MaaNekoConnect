"""Expose the native screen-freeze result as a fail-closed recognition."""

import json
import math
import time

import numpy as np

from maa.custom_recognition import CustomRecognition
from maa.pipeline import JWaitFreezes


_MAX_INT32 = 2**31 - 1
_PARAMETERS = frozenset(
    {"time", "target", "threshold", "method", "rate_limit", "timeout"}
)


def _positive_milliseconds(params, name, default):
    value = params.get(name, default)
    if type(value) is not int or not 1 <= value <= _MAX_INT32:
        raise ValueError(f"{name} must be a positive bounded integer")
    return value


def _parse_parameters(raw):
    params = json.loads(raw)
    if not isinstance(params, dict) or params.keys() - _PARAMETERS:
        raise ValueError("Unsupported freeze parameters")

    duration = _positive_milliseconds(params, "time", 30000)
    timeout = _positive_milliseconds(params, "timeout", 35000)
    rate_limit = _positive_milliseconds(params, "rate_limit", 1000)
    if duration > timeout or rate_limit > timeout:
        raise ValueError("Freeze duration and rate limit must not exceed timeout")

    target = params.get("target", [0, 0, 0, 0])
    if (
        not isinstance(target, list)
        or len(target) != 4
        or any(type(value) is not int or not 0 <= value <= _MAX_INT32 for value in target)
        or target[0] + target[2] > _MAX_INT32
        or target[1] + target[3] > _MAX_INT32
    ):
        raise ValueError("target must be a nonnegative bounded rectangle")

    threshold = params.get("threshold", 0.000001)
    if (
        type(threshold) not in (int, float)
        or not math.isfinite(threshold)
        or not 0 <= threshold <= 1
    ):
        raise ValueError("threshold must be finite and between zero and one")

    method = params.get("method", 1)
    if type(method) is not int or method not in (1, 3, 5):
        raise ValueError("method must be 1, 3, or 5")

    return JWaitFreezes(
        time=duration,
        target=list(target),
        threshold=threshold,
        method=method,
        rate_limit=rate_limit,
        timeout=timeout,
    )


def _valid_image(image):
    return (
        isinstance(image, np.ndarray)
        and image.ndim == 3
        and image.shape[2] == 3
        and image.size > 0
        and image.dtype == np.uint8
    )


def _wait_for_black_screen(context, params, shape):
    # Normalized template matching has zero energy on all-black frames.
    tasker = context.tasker
    controller = tasker.controller
    started = time.monotonic()
    while not tasker.stopping:
        capture = controller.post_screencap().wait()
        if capture.succeeded is not True or tasker.stopping:
            return False
        image = controller.cached_image
        if not _valid_image(image) or image.shape != shape or image.any():
            return False
        elapsed = time.monotonic() - started
        if elapsed >= params.timeout / 1000:
            return False
        if elapsed >= params.time / 1000:
            return True
        time.sleep(
            min(
                params.rate_limit / 1000,
                params.time / 1000 - elapsed,
                params.timeout / 1000 - elapsed,
            )
        )
    return False


class WaitForFrozenScreen(CustomRecognition):
    def analyze(self, context, argv):
        try:
            params = _parse_parameters(argv.custom_recognition_param)
            if not _valid_image(argv.image):
                return None
            if params.target == [0, 0, 0, 0] and not argv.image.any():
                frozen = _wait_for_black_screen(context, params, argv.image.shape)
            else:
                frozen = context.wait_freezes(wait_freezes_param=params)
        except Exception:
            # Exceptions must not escape the native callback or authorize recovery.
            return None
        if frozen is not True:
            return None
        return self.AnalyzeResult(box=argv.roi, detail={"frozen": True})


def register_recovery(registry):
    if registry.register_custom_recognition(
        "WaitForFrozenScreen", WaitForFrozenScreen()
    ) is not True:
        raise RuntimeError("Failed to register WaitForFrozenScreen")
