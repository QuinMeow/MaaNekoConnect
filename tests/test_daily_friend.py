def test_independent_friend_task_uses_batch_not_single_greeting(pipelines):
    choices = pipelines["Daily_FriendTab"]["next"]
    assert "DailyFriend_Batch" in choices
    assert "Daily_FriendGreet" not in choices
    batch = pipelines["DailyFriend_Batch"]
    assert batch["max_hit"] == 1
    assert batch["on_error"] == ["Daily_StopCapture"]
    assert batch["anchor"]["Daily_AfterReward"] == "Daily_Return"


def test_friend_batch_requires_selected_list_and_alert(pipelines):
    guard = pipelines["DailyFriend_Batch"]["all_of"]
    assert "Daily_FriendPage" in guard
    assert any(item.get("template") == "daily/friend_batch.png"
               for item in guard if isinstance(item, dict))
    assert any(item.get("template") == "daily/friend_batch_alert.png"
               for item in guard if isinstance(item, dict))
from pathlib import Path

import numpy as np
from maa.custom_recognition import CustomRecognition




def test_native_batch_requires_selected_list_and_positive_alert(native):
    image = np.zeros((1280, 720, 3), dtype=np.uint8)
    with np.load(Path(__file__).parent / "fixtures/daily/friend_batch.npz", allow_pickle=False) as crops:
        for key, (x, y) in {"title": (284, 87), "tab": (81, 1022),
                            "batch": (514, 941), "alert": (633, 924)}.items():
            crop = crops[key]
            image[y:y + crop.shape[0], x:x + crop.shape[1]] = crop
    assert native.match("DailyFriend_Batch", image)
    assert not native.match("DailyFriend_Batch", (image * 0.7).astype(np.uint8))
    image[924:943, 633:650] = 0
    assert not native.match("DailyFriend_Batch", image)
