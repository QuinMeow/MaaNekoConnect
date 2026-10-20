import pytest


@pytest.mark.parametrize("rounds,cap", [(1, 5), (3, 2), (3, 15)])
def test_rounds_wait_between_runs_and_recovery_does_not_refund_budget(native, pipelines, rounds, cap):
    overrides = {
        name: {"pre_delay": 0, "post_delay": 0, "timeout": 1, "rate_limit": 0}
        for name in pipelines
    }
    graph = {
        "FurnitureTimer_Start": ["[Anchor]FurnitureTimer_Return"],
        "FurnitureEnhance_BeginRound": ["FurnitureEnhance_SessionSpendPermit", "FurnitureEnhance_SessionLimit"],
        "FurnitureEnhance_SessionSpendPermit": ["FurnitureEnhance_Start1"],
        "FurnitureEnhance_Start1": ["FurnitureEnhance_Started"],
        "FurnitureEnhance_Started": ["WaitForTransition"],
        "WaitForTransition": ["NeverMatches"],
        "CommonRecoveryEnter": ["CommonRecoveryDispatch"],
        "CommonRecoveryDispatch": ["CommonRecoveryRecovered"],
        "CommonRecoveryRecovered": ["[Anchor]CommonRecoveryResume"],
        "FurnitureEnhance_RoundFinish": ["Soleil_RequestSupport"],
        "Soleil_RequestSupport": ["FurnitureEnhance_RoundComplete"],
        "FurnitureEnhance_SessionLimit": ["FurnitureEnhance_RoundComplete"],
        "FurnitureEnhance_RoundComplete": ["[Anchor]FurnitureEnhance_OnComplete"],
    }
    # Only the scheduler and native hit counters are under test; business actions are simulated.
    overrides.update({name: {"recognition": "DirectHit", "action": "DoNothing", "next": targets,
                             "pre_delay": 0, "post_delay": 0, "timeout": 1, "rate_limit": 0}
                      for name, targets in graph.items()})
    overrides["FurnitureTimer_Config"]["action"] = "DoNothing"
    overrides["FurnitureTimer_IntervalConfig"]["action"] = "DoNothing"
    overrides["FurnitureSchedule_Permit"]["max_hit"] = rounds
    overrides["FurnitureEnhance_SessionSpendPermit"]["max_hit"] = cap
    overrides["FurnitureEnhance_BeginRound"]["anchor"] = {
        "CommonRecoveryResume": "FurnitureEnhance_RoundFinish",
    }
    overrides["WaitForTransition"]["on_error"] = ["CommonRecoveryEnter"]
    overrides["NeverMatches"] = {
        "recognition": "ColorMatch", "method": 4, "roi": [0, 0, 1, 1],
        "lower": [1, 1, 1], "upper": [2, 2, 2], "count": 1,
    }
    detail = native.run("FurnitureSchedule_Start", overrides)
    names = [node.name for node in detail.nodes]
    assert names.count("FurnitureSchedule_Permit") == rounds
    assert names.count("FurnitureSchedule_FirstRound") == 1
    assert names.count("FurnitureTimer_Start") == rounds - 1
    for name in ("FurnitureEnhance_SessionSpendPermit", "Soleil_RequestSupport", "CommonRecoveryEnter"):
        assert names.count(name) == min(rounds, cap)
    assert names[-1] == "FurnitureSchedule_Complete"
