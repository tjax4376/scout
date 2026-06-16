# Scout dev shortcuts. Prefer scripts/scout.sh for build/start flows.

.PHONY: validate-openspec test test-hawkeye verify-install build-hawkeye-binary

validate-openspec:
	@./scripts/scout.sh validate

test:
	@pytest -q

test-hawkeye:
	@pytest -q tests/hawkeye/

build-hawkeye-binary:
	@./scripts/build_hawkeye_binary.sh

verify-install:
	@./scripts/verify_pipx_install.sh
