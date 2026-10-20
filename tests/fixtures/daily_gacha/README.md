# Advertisement Gacha UI Fixtures

Observed on 2026-10-20 (Asia/Shanghai), game `jp.goodsmile.nekoconne`, controller
720 x 1280. Source captures are ignored local evidence, not committed full screens.

- `free.npz`: title, advertisement-free label and remaining-attempt counter from
  `daily_20261019_185_gacha_ad.png`.
- `confirm.npz`: confirmation title, free-advertisement label, one-draw text and
  bright button from `daily_20261019_186_gacha_ad_start.png`.

Only UI-control crops are retained. Character artwork, account balances and
names are excluded. Values are BGR uint8 arrays; placement is in
`tests/test_daily_gacha.py`. These fixtures prove recognition boundaries, not a
completed advertisement, reward credit or an external vision-provider call.
