# Daily native fixtures

## Scope

Sources are 720 x 1280, game 2.2.0 / JP2 Japanese UI, observed on
2026-10-19 to 20 (Beijing time). Raw captures remain ignored under
`debug/screencap/`. The `daily_20261019_` prefix identifies the session,
not the calendar date of every image.

Only small control/text regions are retained, without account names, friend
avatars, balances, or complete characters. Some controls have a few background
pixels. The `win_text` OCR fixture includes the Win overlay's immediate
background (a fragment of clothing); it is not a production template. Production
battle-result recognition uses native OCR plus the TOP button and brightness,
not MVP artwork or a character template.

PNG templates live in [daily images](../../../assets/resource/image/daily/).
NPZ arrays are `uint8` BGR and load with `allow_pickle=False`.
Fixtures do not operate ADB, network, or real controllers.

## Fixture Files

- `rows.npz`: `header`, `tab`, and Income/Friend/Delivery/VR/Contest/Gold/Gift/Gacha
  full row crops below. Tests paste them at different vertical positions.
- `controls.npz`: named original control crops below, plus `win_text` from
  `daily_20261019_141_contest_progress.png` at `[0,595,350,130]`.
- `holdout.npz`: header/tab/Gold row/button from the later
  `daily_20261019_149_daily_eight_ready.png`, at `[271,117,179,32]`,
  `[45,1018,105,49]`, `[88,340,458,28]`, and `[493,435,138,45]`.
  The `complete` crop is real `(1/1)` from `25_missions` at `[208,340,55,28]`;
  tests place it over each pending progress region in memory to reject replays.
- `weekly.npz`: the remembered weekly selection in
  `daily_20261019_160_after_gold_attempt.png`, retaining header/tab/Close at
  `[271,117,179,32]`, `[45,1018,105,49]`, and `[310,1135,100,100]`.
- `friend_batch.npz`: title/tab/batch/alert controls from
  `daily_20261019_59_friend_greeting.png`, retained as `title` at
  `[284,87,152,40]`, `tab` at `[81,1022,133,39]`, `batch` at
  `[514,941,128,25]`, and `alert` at `[633,924,17,19]`. No friend names,
  avatars, list rows, or account balances are retained. The independent Friend
  module uses the one-click batch control, not the historical single-person
  `greet` crop.
- `guild_ready_holdout.npz`: title and home footer from
  `debug/daily-runs/20261020T043211Z_1792470731856281500/01_login_common_recovery_stopped.png`,
  the 2026-10-20 12:32 stopped-login observation on the Guild root page.
- `guild_members_full.npz`: title and home footer from
  `daily_20261019_177_guild_members.png`. Both new Guild fixtures retain
  `title` at `[0,20,300,80]` and `footer` at `[280,1195,160,75]` only.
  The full title includes the left paw icon and right help control, but no
  guild/member name, avatar, account balance, or list row. Older small title
  crops omitted the paw and could not reproduce the live OCR-cache failure.

The full Guild-title regressions repeat native recognition twice and then run
the real `NavHome_KnownBusinessGate` -> `NavHome_FromKnownBusiness` recheck.
Production OCR keeps exact Japanese title matching and confidence 0.95:
root ROI `[0,20,300,80]`; members ROI `[0,20,210,80]`, which retains the paw
and complete label while excluding the help question mark. A width of 300
on the members page was observed to merge `?` into the title; it is not fixed
by lowering confidence or permitting extra characters. These are offline
regressions from actual UI crops, not successful device navigation evidence.

The holdout is a different screenshot from the task-title source, not a synthetic
font rendering. Relocated rows, replaced completed progress, missing controls,
and 0.75/0.7 dimmed canvases are synthetic regressions, not additional device
observations. Sources shared by templates and fixtures prove observed UI
distinctions, not independent generalization.

## Source Crops

Rectangles are `[x,y,width,height]`. Pending PNGs retain only the listed title
width, excluding the progress; their NPZ row retains the original whole crop.
Progress is separately recognized by native OCR with confidence >= 0.95.

| Name | Local Source | Rectangle | PNG |
| --- | --- | --- | --- |
| `header` | `daily_20261019_25_missions.png` | `[271,117,179,32]` | Original crop |
| `tab` | `daily_20261019_25_missions.png` | `[45,1018,105,49]` | Original crop |
| `pending_income` | `daily_20261019_25_missions.png` | `[88,550,257,28]` | PNG title width 201 |
| `pending_friend` | `daily_20261019_25_missions.png` | `[88,760,369,28]` | PNG title width 309 |
| `pending_delivery` | `daily_20261019_26_missions_middle.png` | `[88,330,240,28]` | PNG title width 183 |
| `pending_gift` | `daily_20261019_29_missions_gap.png` | `[88,303,429,28]` | PNG title width 368 |
| `pending_vr` | `daily_20261019_29_missions_gap.png` | `[88,513,458,28]` | PNG title width 398 |
| `pending_gold` | `daily_20261019_29_missions_gap.png` | `[88,723,458,28]` | PNG title width 331 |
| `pending_contest` | `daily_20261019_27_missions_bottom.png` | `[88,469,278,28]` | PNG title width 219 |
| `pending_gacha` | `daily_20261019_27_missions_bottom.png` | `[88,679,205,28]` | PNG title width 146 |
| `receive` | `daily_20261019_25_missions.png` | `[494,435,137,44]` | Original crop |
| `challenge` | `daily_20261019_29_missions_gap.png` | `[493,398,138,45]` | Original crop |
| `summary` | `daily_20261019_27_missions_bottom.png` | `[88,889,264,28]` | Original crop |
| `milestone` | `daily_20261019_149_daily_eight_ready.png` | `[280,181,52,48]` | Original crop |
| `reward` | `daily_20261019_147_claim_five_ready.png` | `[298,398,128,32]` | Original crop |
| `menu` | `daily_20261019_152_menu_exchange.png` | `[18,448,148,40]` | Original crop |
| `menu_friend` | `daily_20261019_152_menu_exchange.png` | `[218,520,125,97]` | Original crop |
| `friend_title` | `daily_20261019_59_friend_greeting.png` | `[284,87,152,40]` | Original crop |
| `friend_tab` | `daily_20261019_59_friend_greeting.png` | `[81,1022,133,39]` | Original crop |
| `greet` | `daily_20261019_59_friend_greeting.png` | `[505,306,132,45]` | Original crop |
| `friend_batch` | `daily_20261019_59_friend_greeting.png` | `[514,941,128,25]` | Original crop |
| `friend_batch_alert` | `daily_20261019_59_friend_greeting.png` | `[633,924,17,19]` | Original crop |
| `sales_title` | `daily_20261019_88_sales_notification.png` | `[91,201,149,28]` | Original crop |
| `sales_bubble` | `daily_20261019_151_implementation_baseline.png` | `[443,1040,44,48]` | Original crop |
| `map_title` | `daily_20261019_74_surrounding_map.png` | `[52,43,116,28]` | Original crop |
| `map_entry` | `daily_20261019_69_delivery_loaded.png` | `[34,940,118,45]` | Original crop |
| `complete_pin` | `daily_20261019_74_surrounding_map.png` | `[10,604,137,31]` | Original crop |
| `drink_pin` | `daily_20261019_74_surrounding_map.png` | `[468,466,82,106]` | Original crop |
| `delivery_title` | `daily_20261019_79_delivery_auto_team.png` | `[54,42,50,28]` | Original crop |
| `auto_team` | `daily_20261019_79_delivery_auto_team.png` | `[30,974,160,47]` | Original crop |
| `delivery_conditions` | `daily_20261019_79_delivery_auto_team.png` | `[207,448,305,53]` | Original crop |
| `delivery_cost` | `daily_20261019_79_delivery_auto_team.png` | `[231,1064,258,77]` | Original crop |
| `vr_title` | `daily_20261019_102_vr_main.png` | `[51,42,159,28]` | Original crop |
| `vr_main` | `daily_20261019_101_vr_help_closed.png` | `[273,1043,170,30]` | Original crop |
| `vr_free2` | `daily_20261019_102_vr_main.png` | `[509,1027,157,94]` | Original crop |
| `vr_free1` | `daily_20261019_132_vr_remaining.png` | `[509,1027,157,94]` | Original crop |
| `contest_title` | `daily_20261019_115_contest_locked_entry.png` | `[53,42,119,28]` | Original crop |
| `contest_free3` | `daily_20261019_115_contest_locked_entry.png` | `[66,758,146,25]` | Original crop |
| `contest_free2` | `daily_20261019_143_contest_remaining.png` | `[66,758,146,25]` | Original crop |
| `contest_prep_free` | `daily_20261019_139_contest_prepare_once.png` | `[52,1118,157,25]` | Original crop |
| `prep_title` | `daily_20261019_139_contest_prepare_once.png` | `[52,42,123,28]` | Original crop |
| `start` | `daily_20261019_139_contest_prepare_once.png` | `[231,1098,258,61]` | Original crop |
| `result_top` | `daily_20261019_141_contest_progress.png` | `[232,1172,256,60]` | Original crop |
| `exchange_title` | `daily_20261019_153_exchange_current.png` | `[53,42,80,28]` | Original crop |
| `random_tab` | `daily_20261019_154_exchange_random.png` | `[366,1029,323,39]` | Original crop |
| `gold_price` | `daily_20261019_154_exchange_random.png` | `[168,257,155,30]` | Original crop |
| `exchange_offer` | `daily_20261019_154_exchange_random.png` | `[161,307,176,33]` | Original crop |
| `gold_confirm` | `daily_20261019_155_gold_exchange_preview.png` | `[285,181,153,42]` | Original crop |
| `gold_coin` | `daily_20261019_155_gold_exchange_preview.png` | `[202,595,31,31]` | Original crop |
| `gold_quantity` | `daily_20261019_155_gold_exchange_preview.png` | `[348,660,24,27]` | Original crop |
| `gold_slider` | `daily_20261019_155_gold_exchange_preview.png` | `[233,698,255,28]` | Original crop |
| `gold_submit` | `daily_20261019_155_gold_exchange_preview.png` | `[214,885,292,59]` | Original crop |
| `gift_title` | `daily_20261019_106_gift_loaded.png` | `[51,42,159,28]` | Original crop |
| `gift_stage` | `daily_20261019_106_gift_loaded.png` | `[59,377,248,29]` | Original crop |
| `gift_prepare` | `daily_20261019_106_gift_loaded.png` | `[525,483,133,46]` | Original crop |
| `gift_prep_name` | `daily_20261019_108_gift_preparation_ready.png` | `[105,374,205,29]` | Original crop |
| `gift_remaining` | `daily_20261019_106_gift_loaded.png` | `[263,120,48,28]` | Original crop |
| `gacha_title` | `daily_20261019_125_gacha_video.png` | `[54,42,87,28]` | Original crop |
| `ad_free` | `daily_20261019_125_gacha_video.png` | `[274,1011,174,23]` | Original crop |
| `gift_power` | `daily_20261019_108_gift_preparation_ready.png` | `[420,430,175,45]` | Original crop |

## Behavior Boundaries

Native tests require the complete page/control combination, reject missing or
dimmed markers, distinguish `0/1` from `1/1`, exercise bounded attempts and
claim-gate exhaustion, and explicitly switch a remembered weekly tab before
scanning. The OCR cases skip when model files have not been provisioned;
the local final validation used the existing models, not mocked OCR.

The CLI checks nonempty model files before connecting. Models remain deployment
resources, not fixtures; no tests download them or install packages.
Gate/limit flow tests override physical actions with a custom offline controller.
OCR-only matching never performs an action.

Acquisition was manual except the subsequently documented gold exchange,
daily/summary/milestone claims and completed-state reruns. A successful fixture
does not certify automatic Gift battle, new dispatch, advertising playback,
different languages/resolutions, or a complete fresh game day.
See [automation status](../../../docs/zh_cn/develop/daily_automation.md).
