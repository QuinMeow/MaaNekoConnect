# Recovery Native Vision Fixtures

These fixtures retain UI-only crops from 720x1280 observations on 2026-10-19
and 2026-10-20.
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
| `access_denied.npz` | `debug/screencap/daily_20261019_41_after_phone_home.png` | `access_message`, `date_button`, `close` |
| `play_device.npz` | `debug/screencap/daily_20261019_43_denied_title_ready.png` | `device_title`, `device_message`, `device_ok`, `close` |
| `login_failed.npz` | `debug/on_error/2026.10.20-11.06.24.427_Daily_FriendMenu.png` | `login_title`, `login_message`, `device_ok`, `close` |

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
| `access_message` | `[126, 518, 457, 33]` |
| `date_button` | `[211, 635, 298, 62]` |
| `device_title` | `[255, 296, 211, 33]` |
| `device_message` | `[62, 365, 596, 82]` |
| `device_ok` | `[211, 805, 298, 62]` |
| `login_title` | `[225, 295, 270, 40]` |
| `login_message` | `[195, 375, 330, 60]` |
| `close` | `[310, 1135, 100, 100]` |

The access-denied capture was recorded at 23:43 Beijing time on 2026-10-19,
after the user-reported phone login. Its message is `ゲームサーバへのアクセスが拒否されました。`
and its button is `タイトルへ`. The later 23:47 observation shows
`プレイ端末の確認`, a message about playing on another device, and OK.
The user had explicitly stopped operating the phone and authorized local
exploration. These observations do not authorize repeatedly taking over a
session on another device. The matching production crops are
`common_recovery/access_message.png`, `device_title.png`, `device_message.png`,
and `device_ok.png`; access denial reuses the existing title-return button
template `date_button.png`. The date-change fixture remains in
[`../navigation/`](../navigation/README.md).

The 2026-10-20 11:06:24 fault capture has the distinct title
`ログインに失敗しました` and message
`サーバーへの接続に失敗しました / ゲームを終了します`.
It requires exiting the game, unlike the existing return-to-title network
error or play-device confirmation. Only the title, message, OK, and underlying
Close are retained in `login_failed.npz`. Production `login_title.png` and
`login_message.png` use the listed crops; `CommonPlayDeviceButton` reuses the
existing `device_ok.png` template, while this fixture's `device_ok` pixels come
from the new fault capture. The source filename names the interrupted Friend
menu node, not the cause of the error.

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

The original set had no Close/OK positive. The later access-denied,
play-device, and login-failed fixtures retain only their visible Close control underneath the
error, without the surrounding character or home artwork. The generic Close
template and other UI-only dismissal fixtures live in `../navigation/`;
campaign text and notice titles are not required. Device confirmation,
access denial, login failure, date/network errors, and loading must be dispatched before
generic dismissal because a Close can remain visible underneath an error.

Recognition requires both the specific message and its title-return button;
the play-device and login-failed cases require their distinct title, message,
and OK together. Tests remove
each required region and check that other error types do not match. Bounded
flow tests cover access denial -> play-device confirmation -> title TAP ->
positive home -> caller's safe resume, plus persistent network/date/denial/device/login
errors with respective per-Task confirmation caps of 3/3/3/1/1. Login-failed OK
is limited to once in the same Task, then uses the existing shared restart
permit capped at two total restarts; it does not reset any budget or replay
business. The login-failed branch is prioritized before generic Close in
navigation and common recovery. A visible Close
is also placed beneath network/date fixtures in memory to exercise the same
priority and exhaustion boundary; this is a synthetic combination, not another
device observation.

In the tested MaaFramework v5.14.3 behavior, an exhausted `max_hit` node is
skipped rather than taking its `on_error`. An unbounded recognition-only Gate
must therefore select the bounded Confirm or explicit stop branch before
generic Close can be scanned. At the cap, tests require a safe stop with no
generic dismissal, spending replay, or an additional app restart. Counts are not reset on
successful recovery. These fixtures cannot prove that a network-failed upgrade
was not accepted by the server or authorize retrying a spending click, and
offline flow simulations are not real-device acceptance of the automatic chain.
The new login-failed handling has not been revalidated on the real device.
