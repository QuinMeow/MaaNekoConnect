import ast
import json
from pathlib import Path

from maa.context import ContextEventSink


ROOT = Path(__file__).resolve().parents[1]
SUCCESS = "Node.Action.Succeeded"


def test_public_tasks_have_a_human_readable_start_log(pipelines):
    tasks = json.loads((ROOT / "assets/interface.json").read_text("utf-8"))["task"]
    for task in tasks:
        assert pipelines[task["entry"]].get("focus", {}).get(SUCCESS), task["name"]


def test_unrecognized_metrics_keep_their_fields_without_inventing_results(pipelines):
    expected = {
        "DailyDelivery_Start": ("food=", "sweets=", "drive="),
        "DailyDelivery_Collect": ("钻石=",),
        "FurnitureEnhance_Started": ("等级=", "最大耗时="),
    }
    for name, fields in expected.items():
        text = pipelines[name]["focus"][SUCCESS]
        assert "未识别" in text
        assert all(field in text for field in fields)


def test_stop_recovery_and_completion_have_distinct_logs(pipelines):
    for name in ("Daily_StopCapture", "CommonRecoveryStopCapture", "CommonRecoveryEnter"):
        assert "异常" in pipelines[name]["focus"][SUCCESS]
    assert "结束" in pipelines["DailyCore_Done"]["focus"][SUCCESS]


def test_runtime_logs_exclude_repeated_defensive_explanations(pipelines):
    messages = [message for node in pipelines.values()
                for message in node.get("focus", {}).values()]
    for path in (ROOT / "agent").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text("utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                messages.extend(part.value for arg in node.args for part in ast.walk(arg)
                                if isinstance(part, ast.Constant) and isinstance(part.value, str))
    forbidden = ("不重放", "不代表", "安全停止", "不盲点", "未执行盲点", "不推断", "不据此",
                 "不重复", "不重按", "绝不", "有界", "保留消费与恢复预算", "仍停止任务")
    for message in messages:
        assert not any(phrase in message for phrase in forbidden), message


def test_native_focus_reaches_the_action_event_without_changing_workflow(native, pipelines):
    observed = []

    class Logs(ContextEventSink):
        def on_node_action(self, context, noti_type, detail):
            observed.append((str(noti_type), detail.focus))

    sink = Logs()
    assert native.tasker.add_context_sink(sink) is not None
    patch = {"DailyDelivery_Start": {"next": []}}
    names = [node.name for node in native.run("DailyDelivery_Start", patch).nodes]
    assert names == ["DailyDelivery_Start"]
    assert any(focus == pipelines["DailyDelivery_Start"]["focus"] for _, focus in observed)
