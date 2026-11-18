# Delivery UI Fixtures

Observed on 2026-10-20, fixed emulator `127.0.0.1:5557`, 720x1280.
Only map/title/counter and isolated UI controls are retained; no player list,
account currency balance, or character artwork is included.

Map arrays retain `[0,100,710,900]` (x/y/width/height), starting at y=100
rather than y=145 so that the uppermost completed-order label is not clipped.
The account balance strip above this ROI is not retained. The separate native
order counter crop is `[530,102,180,38]`; the title and footer are isolated UI
crops. Retaining the complete top label is necessary to distinguish completed
orders from pending orders, not permission to click an unverified pin.

- `new.npz`: capture `203_delivery_refreshed`, six new orders.
- `running.npz`: `207_delivery_map_after`, one running and five new orders.
- `empty.npz`: `201_map_collected`, all six old orders claimed, zero left.
- `completed.npz`: `199_map`, five completed and one countdown at five seconds.
- `all_busy_current.npz`: 2026-10-20 automatic-run `04_DailyDelivery_Start`,
  five running orders; a neighboring timer obscures the orange burger's left side.
- `mixed_eleven.npz`, `animated_eleven.npz`: subsequent fixed-device captures,
  five running and six pending orders at different breathing-animation phases.
- `glyphs.npz`: isolated boolean food/sweets/drive shapes for synthetic five-color
  backgrounds. This is not evidence of fifteen separately observed live icons.
- `counter_occluded.npz`: a new top-row countdown covers the order counter
  after dispatch, four running and five pending orders. The counter fallback
  requires the covering timer plus independently paired glyphs and marker necks.
  Removing the timer, one glyph, or one marker must reject the map.
- `counter_and_glyph_occluded.npz`: the same nine-order map after two new
  dispatches, six running and three pending. A drink's timer covers the
  neighboring food glyph's bottom-right portion; the left fragment is required.
- `all_started_counter_occluded.npz`: the final 2026-10-20 delivery-only run,
  nine running orders with the counter still covered. The process subsequently
  recognized paid-only refresh, skipped it and returned home.
- `initial_running_current.npz`: 2026-10-21 current map, one running pink sweets
  order and four pending orders. The top countdown overlaps the automatic-map
  refresh text. `delivery_timer_left.png` and `delivery_timer_right.png` retain
  the two ends of that countdown capsule, without the changing digits.
- `two_running_after_dispatch.npz`: fresh overview after the 2026-10-21
  single-order device verification, two running and three pending orders.
  The regression starts with empty local dispatch history.
- `eight_running_current.npz`: fresh 2026-10-21 fixed-device overview with
  eight running and three pending orders, initially with no local history.
  Two overlapping timers hide one capsule's left edge and leading hour zero;
  its visible `H:MM:SS` still belongs to the running blue food pin below it.
- `speedup_close.npz`: the user's 2026-10-21 acceleration dialog, normalized
  from 680x1195 to 720x1280. Only the title and Close control are retained.
  The native flow must click Close, then perform read-only map verification;
  it must never invoke dispatch, acceleration, instant finish or refresh.
- `paid_before.npz`: the 2026-10-21 five-running-order map before the authorized
  100-gem update. The map refresh button is retained, but account balances are not.
  Its enlarged pink sweets glyph supplies the three `sweets_current_*` native
  template sizes; the matching threshold remains 0.90.
- `paid_after.npz`: the matching real post-update map, five preserved running
  orders and six new pending orders. The native regression prepares the baseline
  on `paid_before` then verifies `paid_after` in the same Context, keeping five
  old-order protections. A new lower-left order is beside an old timer; that
  neighboring capsule must not be treated as its own unreadable tag.
- `controls.npz`: `202_delivery_refresh` free confirmation; `205_delivery_auto`
  enabled battery dispatch at 1000; `208_delivery_orange` price 2500;
  `211_delivery_purple` price 10000 (unselected/disabled preparation).
- `action_controls.npz`: black-background UI composites retaining the same
  three dispatch controls, plus the 2026-10-21 real 100-gem update confirmation
  message, gem icon and enabled confirm button. Balance digits are excluded.
  `paid1000` replaces the amount with a real 1000-price crop as a negative;
  `speedup` retains the user's acceleration dialog as another negative.

Pin images are native control crops, not event or character templates. A pin
count mismatch or an unreadable status must block refresh. Fixtures prove only
offline recognition, not server acceptance or a fresh-day full workflow.
`delivery_glyph/` templates retain the dark brown subject only, with a 3x3
smoothing filter and 0.95/1.0/1.1 size variants. The right-hand burger fragment
covers the observed overlap. Native matching still requires the order counter
to equal the deduplicated pin count when readable. If a timer covers the counter,
the independent marker templates use a 45x25 neck crop from the blue food pin
at `[530,510,45,25]` in the 2026-10-20 fixed-device map, with the same three
size variants. The shortened neck avoids the bottom battery bar. Every marker
must pair uniquely with a glyph; unknown counter failures have no fallback.
