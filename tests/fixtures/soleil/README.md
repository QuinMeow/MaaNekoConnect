# Soleil Native Vision Fixtures

These samples are cropped from 720 x 1280 device screenshots observed on
2026-10-19. They do not establish a game version or independent visual
generalization. Only the UI needed by the tests is retained, not balances,
account identifiers, full characters, or complete home screens.

| Fixture | Source screenshot | Purpose |
| --- | --- | --- |
| `idle_slot1.npz` | `debug/soleil_enhance.png` | First furniture selected, ordinary upgrade available |
| `active_slot1.npz` | `debug/soleil_after_start.png` | First furniture running, speedup shown |
| `idle_slot2.npz` | `debug/soleil_second.png` | Second furniture selected, ordinary upgrade available |
| `idle_slot5.npz` | `debug/soleil_slot5_selected.png` | Fifth selected with the first four running |
| `partial_complete.npz` | `debug/soleil_partial_complete.png` | Some upgrades finished, another visible upgrade still running |
| `network_error.npz` | `debug/soleil_ack_failed.png` | Dimmed network-error overlay must reject spending and acknowledgments |
| `home_loading.npz` | `debug/soleil_home.png` | Soleil label visible while its building is still loading |
| `home_ready.npz` | `debug/soleil_reconnect_progress.png` | Soleil building ready for navigation |
| `filters_both_checked.npz` | `debug/soleil_refill_filters.png` | Both supported filter checkboxes checked |
| `filters_reset.npz` | `debug/soleil_refill_filters_reset.png` | Filters reset, both supported checkboxes unchecked |
| `five_active.npz` | `debug/soleil_next_batch_verified.png` | Five visible upgrades active; historical batch screenshot reused for recognition |
| `room_request.npz` | `debug/soleil_room_ready.png` | Store page with enhance and request icons |
| `active_timer.npz` | `debug/soleil_after_start.png` | First item busy, selected preview shows `00:07:58` |

The NPZ arrays are `uint8` BGR images. Tests use
`numpy.load(..., allow_pickle=False)` and reconstruct a black 720 x 1280 frame
from the named regions in `SOLEIL_REGIONS` in
[`conftest.py`](../../conftest.py). The two filter fixtures
retain title, furniture tab, list-top marker, button, first row, filter dialog,
filter tabs, and apply-button regions. `five_active` retains the first five
regions plus the Lv label and ascending arrow, not the filter dialog.
`room_request` retains only title `[0, 20, 160, 70]`, enhance icon
`[610, 420, 85, 90]`, and request icon `[610, 630, 85, 90]`.
`active_timer` retains only title, furniture tab, list-top marker, speedup
button, busy marker `[65, 460, 70, 65]`, selected border `[37, 470, 3, 40]`,
and timer `[520, 1000, 125, 65]`. The timer crop contains the `00:07:58`
countdown and its small completion label, not an animated loading character.
It intentionally omits the orange eligibility mark: an already-busy item
must be selectable for timer monitoring even when no candidate is available.

Tests run real MaaFw recognition, not gameplay actions. The test controller
rejects input; subprocess and network calls are blocked. Assertions inspect
`RecognitionDetail.hit`, not merely recognition-job success. The old batch-mode
checkpoint of 31 cases is historical, not current refill-mode acceptance.

## Synthetic Cases

Current checks are owned by the furniture-round, filter, shop, and timer modules,
one test file each; see the [test policy](../../README.md). They retain selected
idle-slot positives, busy/overlay spending negatives, required-region removal,
all 32 busy-marker combinations, four idempotent filter combinations, and
acknowledgment after grid reordering. Timer tests retain fresh-page validation
after a freeze. Native OCR checks read both observed countdown crops when model
weights are available.

The following larger synthetic matrices describe historical validation, not
the complete current suite. Frames were composed in memory, not independently
captured NPZ fixtures:

- The first-slot hammer crop `[65, 460, 70, 65]` from `partial_complete` is
  relocated onto `idle_slot1` for all 32 first-row busy/idle combinations.
  Orange eligibility marks are retained. The actual `FurnitureEnhance_Scan.next` must
  match `BusyN` before `SelectN` when both the hammer and mark are present.
- A separate first-slot-idle / fifth-slot-busy case clears the fifth eligibility
  mark and proves that the first slot may start without waiting for the fifth.
- Four independent filter-checkbox combinations are composed from
  `filters_both_checked` and `filters_reset` using checkbox regions
  `[88, 635, 40, 42]` and `[88, 780, 40, 42]`. Tests verify mutually exclusive
  checked/unchecked recognition and idempotent On/Off dispatch: already-correct
  states do not toggle; incorrect states choose Enable/Disable.
- Selected red-border stripes are relocated between slots, and required page,
  list-top, label, or arrow regions are removed to exercise the relevant guards.
  Direct selected-slot observations exist for slots 1, 2, and 5. Red-border x
  coordinates are `(37, 167, 297, 427, 555)`, not an exactly uniform sequence;
  the fifth-slot x=557 assumption missed the real selected border.
- Five relocated red-border cases on `active_slot1` verify that selected-busy
  checks require the current slot's border. An old speedup preview must not make
  a different newly clicked slot appear busy before its selection is confirmed.
- A second set of 32 busy/idle combinations verifies the actual
  `FurnitureTimer_Sample.next` dispatch: select the first positive busy slot for timer
  monitoring, or finalize the fallback interval when no visible item is busy. Separate
  selected-border cases protect the monitored preview from stale selection.
- The running first-row crop is removed from `active_slot1` to verify that a
  successful start acknowledgment uses selected-detail speedup state rather
  than assuming the furniture stayed in its original grid slot after sorting.

## Safety Boundaries

An orange eligibility mark is not proof of idleness. Busy-first dispatch and
the selected-detail busy recheck with the current slot's border are essential.
Post-spend acknowledgment intentionally does not fix the selected border or
hammer to its previous slot, allowing automatic filter/sort movement.
Ordinary-button template
matching alone can match the dimmed network-error page because normalized
matching is brightness-invariant, so full positive page, selection, and button
guards are tested together. Unrelated pages must not spend.
After timer monitoring, normal-brightness button colors are also required
before treating a preview as newly ready or still busy. A dimmed speedup
button can retain a positive text-template score; a historical synthetic dimming
case verified the brightness gate. That dedicated case is not retained in the
lightweight suite.
The default existing-sort path deliberately does not require a Lv label or
ascending arrow. Request actions require both the store-page guard and the
request icon; other fixtures must reject them.

Some samples are also template sources. Passing these cases does not establish
independent screenshot generalization, other resolutions/languages/accounts,
global queue counting, general countdown OCR accuracy, real device input, request delivery,
or long-running refill completion. Historical five-item batch evidence is not
live acceptance of the new default refill mode.
