# Journal: --embed-batch CLI flag

## Context

User asked to expose Scout's embed HTTP batch size (hardcoded 16) as CLI flag after learning LM Studio eval batch (2048–4096) is a separate server-side setting.

## Discussion

- Scout batch = chunks per `POST /v1/embeddings` request (client-side).
- LM Studio eval batch = GPU inference batching (server-side). Not the same knob.
- Flag added for `reindex` and `setup` only; API reindex uses default 4096 for now.

## Code changed

- `scout/indexing.py` — `run_reindex(..., embed_batch_size=...)`
- `scout/cli/main.py` — `--embed-batch N`, usage text, validation `>= 1`
- `scout/setup/runner.py` — pass through to `run_reindex`
- `tests/cli/test_embed_batch.py` — flag parse + batching unit tests

## Test plan

- `pytest tests/cli/test_embed_batch.py -q`
- Manual: `scout scout reindex --embed-batch 128`
