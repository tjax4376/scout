# Scout Unified Setup — Tasks

## 1. OpenSpec

- [x] 1.1 Create proposal, design, delta specs, tasks

## 2. API URL config

- [x] 2.1 Add `api_base_url` to ScoutConfig with load/save/migration
- [x] 2.2 Implement `scout/setup/api_url.py` helpers
- [x] 2.3 Update `scout serve` to bind from parsed URL

## 3. Setup module

- [x] 3.1 Create `scout/setup/prompts.py` (branch menu, API URL, keys, agent)
- [x] 3.2 Create `scout/setup/workspace.py` (local path + git clone)
- [x] 3.3 Create `scout/setup/embed.py` (embed provider flow)
- [x] 3.4 Create `scout/setup/runner.py` (orchestration)
- [x] 3.5 Refactor `scout/cli/main.py` to delegate setup

## 4. Tests and docs

- [x] 4.1 Add `tests/test_setup.py`
- [x] 4.2 Extend integration tests
- [x] 4.3 Update README, journal, memory cards
