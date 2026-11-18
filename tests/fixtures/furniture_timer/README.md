# Furniture Timer OCR Fixtures

`countdown_10_59.npz` stores only the `uint8` BGR timer crop at
`[520, 1000, 125, 65]` from `debug/soleil_next_batch_verified.png`, observed on
2026-10-19. It contains the completion label and `00:10:59`, not account
identifiers, balances, or characters.

Native OCR tests read this crop and the existing `soleil/active_timer.npz`
`00:07:58` sample. Shortest/longest absolute deadlines and unreadable-result
fixed fallback are separate unit tests with simulated OCR results.
These are offline tests; controller input, process execution, and
network access are rejected. They do not prove live queue completion or OCR
support for unseen fonts/resolutions. Model weights are provisioned separately
and remain ignored rather than committed fixtures.
