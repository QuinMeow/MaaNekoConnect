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
- `controls.npz`: `202_delivery_refresh` free confirmation; `205_delivery_auto`
  enabled battery dispatch at 1000; `208_delivery_orange` price 2500;
  `211_delivery_purple` price 10000 (unselected/disabled preparation).

Pin images are native control crops, not event or character templates. A pin
count mismatch or an unreadable status must block refresh. Fixtures prove only
offline recognition, not server acceptance or a fresh-day full workflow.
