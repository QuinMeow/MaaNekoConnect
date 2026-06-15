from __future__ import annotations

import json

from maa.custom_action import CustomAction

from .action import (
    RunStatus,
    StartOutcome,
    parse_action_config,
    run_automation,
)
from .models import Candidate, ScanSnapshot
from .parsing import candidate_from_ocr
from .priority import ATTRIBUTE_ORDER, FLOWER_ORDER


_OPEN_ENTRY = {
    "Food": "SoleilFlowerbedOpenFood",
    "Sweets": "SoleilFlowerbedOpenSweets",
    "Drink": "SoleilFlowerbedOpenDrink",
    "Customer Service": "SoleilFlowerbedOpenCustomerService",
    "Work Speed": "SoleilFlowerbedOpenWorkSpeed",
    "Stamina": "SoleilFlowerbedOpenStamina",
}

_FIELD_NODE = {
    "title": "SoleilFlowerbedReadTitle",
    "levels": "SoleilFlowerbedReadLevels",
    "bonuses": "SoleilFlowerbedReadBonuses",
    "resources": "SoleilFlowerbedReadResources",
    "duration": "SoleilFlowerbedReadDuration",
}


def _task_succeeded(task) -> bool:
    return task is not None and bool(getattr(task.status, "succeeded", False))


def _nodes_by_name(task) -> dict:
    return {
        node.name: node
        for node in getattr(task, "nodes", ())
        if getattr(node, "completed", False)
    }


def _recognition_result(node):
    recognition = getattr(node, "recognition", None)
    if recognition is None or not recognition.hit:
        raise ValueError(f"recognition did not hit for {getattr(node, 'name', '')}")
    result = recognition.best_result
    if result is None:
        raise ValueError(f"recognition result missing for {getattr(node, 'name', '')}")
    return result


class MaaFlowerbedBackend:
    def __init__(self, context):
        self.context = context
        self._verified_key = None

    def _run_required(self, entry: str):
        task = self.context.run_task(entry)
        if not _task_succeeded(task):
            raise RuntimeError(f"pipeline subflow failed: {entry}")
        return task

    def _select_flower(self, index: int) -> None:
        self._run_required("SoleilFlowerbedResetFlowerList")
        if index == len(FLOWER_ORDER) - 1:
            self._run_required("SoleilFlowerbedScrollToLastFlower")
        self._run_required(f"SoleilFlowerbedSelectFlower{index}")

    def _open_attribute(self, attribute: str) -> None:
        self._run_required(_OPEN_ENTRY[attribute])

    def _close_popup_best_effort(self) -> None:
        try:
            self.context.run_task("SoleilFlowerbedClosePopup")
        except Exception:
            pass

    def _read_open_popup(self, flower: str, attribute: str) -> Candidate:
        task = self._run_required("SoleilFlowerbedReadPopupEntry")
        nodes = _nodes_by_name(task)
        fields = {}
        scores = []
        for field, node_name in _FIELD_NODE.items():
            if node_name not in nodes:
                raise ValueError(f"popup field node missing: {node_name}")
            result = _recognition_result(nodes[node_name])
            fields[field] = result.text
            scores.append(float(result.score))

        enabled_node = nodes.get("SoleilFlowerbedUpgradeButtonEnabled")
        text_node = nodes.get("SoleilFlowerbedUpgradeButtonText")
        if enabled_node is None or text_node is None:
            raise ValueError("upgrade button state is incomplete")
        _recognition_result(enabled_node)
        text_result = _recognition_result(text_node)
        scores.append(float(text_result.score))
        fields.update(
            {
                "button_enabled": True,
                "active": False,
                "capped": False,
                "confidence": min(scores),
            }
        )
        return candidate_from_ocr(
            flower=flower,
            expected_attribute=attribute,
            fields=fields,
        )

    def _recognition_hit(self, entry: str, node_name: str) -> bool:
        task = self.context.run_task(entry)
        if task is None:
            return False
        node = _nodes_by_name(task).get(node_name)
        if node is None:
            return False
        recognition = getattr(node, "recognition", None)
        return bool(recognition is not None and recognition.hit)

    def _detect_unavailable_state(self, attribute: str) -> str:
        if self._recognition_hit(
            "SoleilFlowerbedDetectActiveEntry",
            "SoleilFlowerbedDetectActive",
        ):
            return "active"
        if attribute == "Customer Service" and self._recognition_hit(
            "SoleilFlowerbedDetectCappedEntry",
            "SoleilFlowerbedDetectCapped",
        ):
            return "capped"
        raise RuntimeError("candidate state could not be confirmed")

    def scan(self) -> ScanSnapshot:
        candidates = []
        active_count = 0
        self._verified_key = None
        for flower_index, flower in enumerate(FLOWER_ORDER):
            self._select_flower(flower_index)
            for attribute in ATTRIBUTE_ORDER:
                self._open_attribute(attribute)
                try:
                    try:
                        candidate = self._read_open_popup(flower, attribute)
                    except (RuntimeError, ValueError):
                        self._close_popup_best_effort()
                        state = self._detect_unavailable_state(attribute)
                        if state == "active":
                            active_count += 1
                        continue
                    self._run_required("SoleilFlowerbedClosePopup")
                    candidates.append(candidate)
                except Exception:
                    self._close_popup_best_effort()
                    raise
        return ScanSnapshot(
            active_count=active_count,
            candidates=tuple(candidates),
        )

    def verify(self, proposed: Candidate) -> Candidate | None:
        try:
            flower_index = FLOWER_ORDER.index(proposed.flower)
            self._select_flower(flower_index)
            self._open_attribute(proposed.attribute)
            verified = self._read_open_popup(proposed.flower, proposed.attribute)
        except (RuntimeError, ValueError):
            self._close_popup_best_effort()
            self._verified_key = None
            return None
        if verified != proposed:
            self._close_popup_best_effort()
        self._verified_key = verified.idempotency_key
        return verified

    def start(self, proposed: Candidate) -> StartOutcome:
        if proposed.idempotency_key != self._verified_key:
            return StartOutcome.UNKNOWN
        self._verified_key = None
        action = self.context.run_task("SoleilFlowerbedConfirmStart")
        if not _task_succeeded(action):
            return StartOutcome.FAILED
        if not self._recognition_hit(
            "SoleilFlowerbedConfirmStartedEntry",
            "SoleilFlowerbedConfirmStartedState",
        ):
            return StartOutcome.UNKNOWN
        return StartOutcome.CONFIRMED


class SoleilFlowerbedAutoAction(CustomAction):
    def run(self, context, argv):
        try:
            values = json.loads(argv.custom_action_param or "{}")
            config = parse_action_config(values)
            result = run_automation(config, MaaFlowerbedBackend(context))
        except (TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            print(json.dumps({"status": "stopped", "reason": str(exc)}, ensure_ascii=False))
            return False

        output = {
            "status": result.status.value,
            "planned": [
                {
                    "key": item.candidate.idempotency_key,
                    "deadline_rating": item.deadline_rating,
                }
                for item in result.planned
            ],
            "started": [
                candidate.idempotency_key
                for candidate in result.started
            ],
            "stop_reason": result.stop_reason,
        }
        print(json.dumps(output, ensure_ascii=False))
        return result.status is not RunStatus.STOPPED
