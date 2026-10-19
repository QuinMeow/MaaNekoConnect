def build_soleil_overrides(
    use_existing_sort: bool = True,
    sort_order: str = "lv_asc",
    only_placed: bool = True,
    only_upgradeable: bool = True,
    auto_request: bool = True,
) -> dict:
    """Build the same node overrides as the active Soleil PI options."""
    switches = {
        "use_existing_sort": use_existing_sort,
        "only_placed": only_placed,
        "only_upgradeable": only_upgradeable,
        "auto_request": auto_request,
    }
    for name, value in switches.items():
        if not isinstance(value, bool):
            raise ValueError(f"{name} must be a bool")
    if not isinstance(sort_order, str) or sort_order not in ("lv_asc", "lv_desc"):
        raise ValueError("sort_order must be 'lv_asc' or 'lv_desc'")

    overrides = {
        "FurnitureEnhance_Prepare": {
            "next": ["FurnitureEnhance_ScrollTop" if use_existing_sort else "FurnitureFilter_OpenSort"]
        },
        "FurnitureEnhance_AfterStart": {
            "anchor": {
                "FurnitureEnhance_PostRound":
                    "FurnitureEnhance_ReturnForRequest" if auto_request else "FurnitureEnhance_RoundComplete"
            }
        },
    }
    if not use_existing_sort:
        overrides.update(
            {
                "FurnitureFilter_Direction": {
                    "next": ["FurnitureFilter_AscendingReady", "FurnitureFilter_FlipToAscending"]
                    if sort_order == "lv_asc"
                    else ["FurnitureFilter_DescendingReady", "FurnitureFilter_FlipToDescending"]
                },
                "FurnitureFilter_FilterPlaced": {
                    "next": ["FurnitureFilter_PlacedOn" if only_placed else "FurnitureFilter_PlacedOff"]
                },
                "FurnitureFilter_FilterUpgradeable": {
                    "next": ["FurnitureFilter_UpgradeableOn" if only_upgradeable else "FurnitureFilter_UpgradeableOff"]
                },
            }
        )
    return overrides



def build_schedule_overrides(rounds=1, interval=60, wait_mode="single"):
    """Configure finite rounds and the shared interruptible wait action."""
    if type(rounds) is not int or not 1 <= rounds <= 10000:
        raise ValueError("rounds must be an integer from 1 to 10000")
    if type(interval) is not int or not 10 <= interval <= 86400:
        raise ValueError("interval must be an integer from 10 to 86400 seconds")
    if not isinstance(wait_mode, str) or wait_mode not in ("single", "fixed", "shortest", "longest"):
        raise ValueError("wait_mode must be single, fixed, shortest or longest")
    if wait_mode == "single" and rounds != 1:
        raise ValueError("single wait_mode requires exactly one round")
    return {
        "FurnitureSchedule_Permit": {"max_hit": rounds},
        "FurnitureTimer_Config": {
            "custom_action_param": {
                "op": "config",
                "mode": "fixed" if wait_mode == "single" else wait_mode,
            }
        },
        "FurnitureTimer_IntervalConfig": {
            "custom_action_param": {"op": "interval", "seconds": interval}
        },
    }
