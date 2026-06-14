# Journal: Auto embed batch probe

## Context

User wanted hardware-aware max embed batch — 4096 still not saturating LM Studio (eval batch 2048–4096 is server-side; client batch was separate).

## Discussion

- Raw RAM scan alone insufficient — GPU VRAM on embed server unknown from client.
- Approach: RAM-derived ceiling caps probe range; live exponential + binary search against provider finds real max.
- Uses p90 chunk length from built chunks for realistic probe payload.
- Result cached in `config.yaml` as `embed.embed_batch_size`; skip probe on later runs unless `--reprobe-embed-batch`.
- `--embed-batch N` still manual override; omit flag for auto.

## Code changed

- `scout/embed/batch_probe.py` — hardware ceiling, probe, resolve
- `scout/config.py` — `embed_batch_size` field
- `scout/indexing.py` — probe before embed, cache result
- `scout/cli/main.py` — `--reprobe-embed-batch`, auto default
- `tests/embed/test_batch_probe.py`

## Test plan

- `pytest tests/embed/test_batch_probe.py -q`
- Manual: `scout scout reindex --reprobe-embed-batch` → prints probed batch
