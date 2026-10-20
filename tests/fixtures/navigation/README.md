# Navigation UI Fixtures

These fixtures are UI-only crops of 720 x 1280 screenshots observed on
2026-10-19. The original navigation set reused earlier captures; the popup set
below was captured during an authorized live exploration. Balances,
account identifiers, complete screens, and full characters are not retained.

| Fixture | Existing source screenshot | Retained regions |
| --- | --- | --- |
| `home_ready.npz` | `debug/soleil_reconnect_progress.png` | `home_label`, `home_building` |
| `home_holdout.npz` | `debug/common_recovery_network_home_verified.png` | `home_label`, `home_building` |
| `home_loading.npz` | `debug/soleil_home.png` | `home_label`, `home_building` |
| `cafe.npz` | `debug/soleil_room_ready.png` | `cafe_title`, `enhance_icon`, `footer_home`, `footer_back` |
| `enhance.npz` | `debug/soleil_enhance.png` | `enhance_title`, `furniture_tab`, `footer_home`, `footer_back` |
| `transition_loading.npz` | `debug/soleil_room_return.png` | `cafe_title`, `enhance_icon`, `footer_home`, `footer_back` |

`soleil_room_return.png` contains a loading transition, not a successful return
to the cafe. The retained rectangles exclude the central comic artwork. The
source filename is not evidence of its page type.

| Region | `[x, y, width, height]` |
| --- | --- |
| `home_label` | `[530, 1205, 155, 65]` |
| `home_building` | `[535, 1105, 140, 110]` |
| `cafe_title` / `enhance_title` | `[0, 20, 160, 70]` |
| `enhance_icon` | `[610, 420, 85, 90]` |
| `furniture_tab` | `[30, 1088, 215, 55]` |
| `footer_home` | `[280, 1195, 160, 75]` |
| `footer_back` | `[95, 1195, 115, 75]` |

NPZ values are `uint8` BGR and loaded with `allow_pickle=False`. The test
reconstructs a black 720 x 1280 canvas and restores only the named crops.

Two production PNG templates in `assets/resource/image/navigation/` were
cropped from the same `soleil_room_ready.png` capture: `footer_home.png` is
`[295, 1215, 130, 40]`, and `footer_back.png` is `[115, 1214, 74, 39]`.
They include only the interior button UI. Other navigation templates reuse
the existing Soleil building/label, store title, and enhance icon crops.

The tests run native recognition only. The custom controller rejects input,
and process/network entry points are blocked. They inspect actual recognition
hits, not just native job success. Dimmed negatives are synthetic factors 0.5
and 0.75, not separately observed overlays. Required-region removal, isolated
footers, and uniform black/gray/white frames are also synthetic negatives.

These crops cannot prove arrival after a real click, general support for
unknown modals, all dimming levels, other languages/resolutions, or every game
page exposing a similar footer. Some positive images are template sources;
the later home capture is a separate observation, not independent general
visual validation. Real zero-consumption navigation smoke tests remain a
separate acceptance step.

## Cross-Day and Login Popup Observations

Source: game 2.2.0, JP2, Japanese, 720 x 1280, 2026-10-19 23:02-23:13 CST
(2026-10-20 JST). Original files are ignored local evidence under
`debug/screencap/daily_20261019_*.png`. Only UI crops are retained here.

| Fixture | Source suffix | Regions `[x,y,width,height]` |
| --- | --- | --- |
| `date_changed` | `03_reset_notice` | `date_message` `[255,515,215,40]`, `date_button` `[211,635,298,62]` |
| `monthly_bonus` | `10_monthly_ready` | `reward_banner` `[32,97,47,52]`, `reward_panel` `[0,1150,720,34]`, `reward_blank` `[280,1200,160,55]` |
| `event_bonus` | `12_event_dismiss` | same shared reward chrome regions |
| `half_bonus` | `14_half_continue` | same shared reward chrome regions |
| `event_promo` | `15_half_dismiss` | `promo_continue` `[240,1204,240,27]`, home regions above |
| `gacha_promo` | `18_gacha_promo_dismiss` | same regions as `event_promo` |
| `notice_list` | `20_pickup2_dismiss` | `close` `[310,1135,100,100]`, home regions above |

After the user's generalization request, production uses only the shared
banner ornament, continue text and circular Close. Reward panel/blank colors
are native ColorMatch checks. Reward titles, item/stamp details, notice titles
and checkbox text are not retained or required. There are no per-campaign
templates. Date templates live in `image/common_recovery/`; the generic popup
templates live in `image/navigation/`.

Observed overlay crops preserve their dimmed home UI so tests reject false
home arrival. Removing each required shared marker and multiplying reward/Close
brightness by 0.75 are synthetic negatives. The reward-panel and Close brightness
gates are not applied to promo text, whose background is already dim. Native
flow tests simulate different-length chains, popup recurrence after returning
home, shared dismissal exhaustion, and date-change relogin without business
actions. Inputs are simulated callbacks, never ADB. The budget flow uses a
shortened limit of three to keep execution lightweight, not a production reset.

Templates and most positives share source images. The other reward captures
and second promo are separate observations of the same shared chrome; they
do not prove arbitrary future layouts. No characters or promo artwork are
used as markers. Close is generic and no longer depends on notice titles/tabs.
A synthetic date-error screen includes a matching Close underneath: flow
tests prove that the special error confirmation wins instead of closing it.
