# Recovery Native Vision Fixtures

These fixtures retain UI-only crops from 720x1280 observations on 2026-10-19.
They do not retain account identifiers, balances, full screens, or characters.
The title fixture names describe the source background, not retained artwork.

| Fixture | Original local capture | Retained regions |
| --- | --- | --- |
| `network_stable.npz` | `debug/soleil_refill_final_network.png` | `network_message`, `network_confirm` |
| `network_timeout.npz` | `debug/soleil_refill_after_timeout.png` | `network_message`, `network_confirm` |
| `title_truck.npz` | `debug/soleil_refill_reconnect2.png` | `title_tap`, `title_logo` |
| `title_characters.npz` | `debug/soleil_title.png` | `title_tap`, `title_logo` |
| `title_loading.npz` | `debug/soleil_refill_home_recovered.png` | `title_tap`, `title_logo`, `loading_text` |
| `enhance_loading.npz` | `debug/soleil_refill_recovered_start_loading.png` | `loading_text` |
| `home_ready_holdout.npz` | `debug/soleil_refill_home_recovered2.png` | `home_building`, `home_text` |

Each NPZ stores named `uint8` BGR crops readable with NumPy and
`allow_pickle=False`. Tests reconstruct a black 720x1280 canvas and place only
these crops at their original `[x, y, width, height]` positions:

| Region | Position |
| --- | --- |
| `network_message` | `[185, 508, 350, 54]` |
| `network_confirm` | `[211, 635, 298, 62]` |
| `title_tap` | `[248, 1064, 225, 32]` |
| `title_logo` | `[219, 955, 283, 34]` |
| `loading_text` | `[549, 1198, 108, 27]` |
| `home_building` | `[535, 1105, 140, 110]` |
| `home_text` | `[530, 1205, 155, 65]` |

Production templates partly share capture sources with these fixtures. These
are regressions for observed distinctions, not independent recognition
generalization or support for other languages/resolutions. The home-ready
sample is a later holdout for the existing Soleil building/label templates.
Other game-page negatives reuse the documented crops in `../soleil/` without
copying full source images or additional character pixels.

Recognition cases run real MaaFramework recognition without Pipeline actions;
assertions inspect `RecognitionDetail.hit`, not just job success. The merged
recovery module also runs bounded flow cases with explicitly simulated app
start/stop callbacks. Other inputs, subprocesses, and network connections are
blocked; none of these cases operate a real device.

The title loading observation deliberately retains both the TAP button and
title logo. They remain visible during loading, so a positive title match
alone is not permission to click again. Pipeline structure must prioritize
the positive loading branch before the title-tap branch. No inverse check
inside an `And` is used as an absence proof.

Loading ellipsis dots animate between captures. The fixtures retain the full
observed text region, while the production template uses only the static word
`Loading` at `[554, 1200, 73, 20]`. This preserves the recognition threshold
instead of lowering it to accommodate changing dots.

There is no approved generic Close/OK recovery positive here. The circular
Close control visible beneath network/filter overlays belongs to the obscured
underlying page; it must not become a generic modal-dismissal template.
These fixtures cannot prove that a network-failed upgrade was not accepted by
the server or authorize retrying a spending click.
