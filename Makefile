# Scout dev shortcuts. Prefer scripts/scout.sh for build/start flows.

.PHONY: validate-openspec test

validate-openspec:
	@./scripts/scout.sh validate

test:
	@pytest -q
