# Navigation UI Fixtures

These fixtures are UI-only crops of existing 720 x 1280 screenshots observed on
2026-10-19. No new device capture or input was used to produce them. Balances,
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
