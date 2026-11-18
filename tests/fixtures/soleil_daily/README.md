# Soleil Daily Native Fixtures

Observed on 2026-10-21, game 2.2.0 (versionCode 125), Japanese 720 x 1280.
NPZ files contain uint8 BGR crops only and load with allow_pickle=False.
Raw captures remain ignored; no device, network or account identifiers are
needed by the tests. Kept regions cover page titles, navigation controls,
quota labels, collection markers and the immediate bath background. A small
top-bar crop adds only the duck icon and duck count, not other currencies.

- `bath_small_two`: live ADB capture 03, two remaining baths.
- `bath_zoom_one`: SDK cached frame 17, one remaining bath at a larger scale.
- `bath_small_zero`: live ADB capture 26, zero remaining baths.
- `bath_zoom_zero`: explicit post-action frame 38, zero remaining baths.
- `bath_clipped_one` and `bath_clipped_zero`: SDK frames 18 and 19, quota label
  clipped by excessive zoom. These are negative recognition cases.
- `duty`: ADB capture 00, duty page labels and the auto-assignment button.
- `room`: previously captured shop controls and an unselected bath tab.

The old `daily_20261019_` capture prefix is a session label, not the capture date.
SDK `Screencap` actions can save the most recent cached recognition frame;
frames 17-19 prove visible states, not that the immediately preceding action
caused them. Frame 38 was explicitly refreshed using `post_screencap`.

The two-collection native test replays these real crops in sequence. It is not
an assertion that the nonzero daily entry was run end-to-end on the device.

Duck-count crops at `[470, 25, 170, 50]` retain the observed balances `3`, `6`,
`7`, and `7` from frames 03, 17, 26, and 38 respectively. The first three
provide native OCR evidence for per-collection differences `+3` and `+1`.
`bath_duck_icon.png` is the unmodified `[482, 34, 32, 31]` UI crop from frame 03.
The `1..10` random reward range is user-provided on 2026-10-21; these captures
do not independently establish its full distribution.
