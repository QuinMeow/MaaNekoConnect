"""Read Android's resumed activity through the bound Maa controller only."""

import json
import re

from maa.custom_recognition import CustomRecognition


PACKAGE = "jp.goodsmile.nekoconne"
ACTIVITY_COMMAND = "dumpsys activity activities"
_MARKER = re.compile(r"^\s*(?:topResumedActivity\s*=|mResumedActivity\s*:|ResumedActivity\s*:)")
_COMPONENT = re.compile(r"ActivityRecord\{[^}\r\n]*\bu\d+\s+([a-zA-Z][\w.]*)/[^\s}]+")


def resumed_package(output):
    if not isinstance(output, str) or len(output) > 2_000_000:
        return None
    packages = set()
    for line in output.splitlines():
        if not _MARKER.match(line):
            continue
        match = _COMPONENT.search(line)
        if match is None:
            return None
        packages.add(match[1])
    return packages.pop() if len(packages) == 1 else None


class DailyLoginAppState(CustomRecognition):
    def analyze(self, context, argv):
        try:
            params = json.loads(argv.custom_recognition_param)
            if (not isinstance(params, dict) or set(params) != {"foreground"}
                    or type(params["foreground"]) is not bool):
                return None
            tasker = context.tasker
            if tasker.stopping:
                return None
            job = tasker.controller.post_shell(ACTIVITY_COMMAND, timeout=3000).wait()
            if job.succeeded is not True or tasker.stopping:
                return None
            package = resumed_package(job.get())
            if package is None or (package == PACKAGE) is not params["foreground"]:
                return None
            return self.AnalyzeResult(box=argv.roi, detail={"foreground": package == PACKAGE})
        except Exception:
            return None


def register_login(registry):
    if registry.register_custom_recognition("DailyLoginAppState", DailyLoginAppState()) is not True:
        raise RuntimeError("Failed to register DailyLoginAppState")
