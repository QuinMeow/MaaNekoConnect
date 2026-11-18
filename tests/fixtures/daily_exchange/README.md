# Exchange Currency Fixtures

Observed 2026-10-21, game 2.2.0 / JP2, 720 x 1280. Source audit:
`debug/evidence/task-audit-20261021/16_DailyExchange_Start/`.

`mixed_currency.npz` retains only exchange title `[35,25,120,60]`, random tab
`[350,1015,350,75]`, and each of the four slots' currency marker and offer
button. Button rectangles are `[150,300,195,45]`, `[485,300,195,45]`,
`[150,500,195,45]`, `[485,500,195,45]`; each currency rectangle starts at
`[button_x+24,button_y-40]` with size `[40,36]`. The first marker is diamonds,
the other three are gold. No account balance, item art, ownership or name is
retained. Gold marker production templates are `[512,262,23,23]` and
`[176,463,23,23]`; the lower row has a distinct subpixel raster phase.
Both require 0.97 rather than relaxing confidence for the observed variation.
The lower offer button at `[161,508,176,33]` likewise supplements the original
upper-row template at the same 0.97 threshold.

`non_gold_confirm.npz` keeps only the generic confirmation title
`[270,165,190,65]` and current Close control `[310,1135,100,100]`. The original
dialog is the first diamond item with stock 1/1, without quantity/price slider.
It never authorizes a purchase. The same Close crop supplements exchange's
local close recognition at threshold 0.97; title and brightness remain required.

Arrays are original uint8 BGR crops loaded with `allow_pickle=False`.
Missing currency is synthesized only in tests and never authorizes opening.
Offline tests replay three gold previews, one unit each, with the original
final currency/quantity/slider guards. They do not certify a device purchase.
