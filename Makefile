.PHONY: reproduce preflight-v2 smoke-v2 smoke lint packet-validate reproduce-tables validate-locks validate-validation reviewer-test unit-test test-all help

PYTHON ?= python

help:
	@echo "Targets: reproduce, reproduce-tables, validate-locks, validate-validation, reviewer-test, unit-test, preflight-v2, smoke-v2"

preflight-v2:
	$(PYTHON) code/scripts/preflight_phase4_v2.py --mode smoke --agent-type scripted

smoke: smoke-v2

smoke-v2:
	$(PYTHON) code/scripts/run_phase4_v2.py --mode smoke --agent-type scripted --run-id reviewer_smoke --output-root runs --overwrite --disable-hf-backup

reproduce: preflight-v2 smoke-v2
	@echo "Reviewer smoke reproduction complete."

lint:
	$(PYTHON) -m ruff check code

packet-validate:
	$(PYTHON) code/scripts/build_final_supported_packet.py --output-root reports/paper

reproduce-tables: packet-validate

validate-locks:
	$(PYTHON) code/scripts/validate_locked_scoring_targets.py

validate-validation:
	$(PYTHON) code/scripts/validate_validation_artifacts.py

unit-test:
	$(PYTHON) -m pytest -q

reviewer-test: lint reproduce-tables validate-locks validate-validation preflight-v2 unit-test
	@echo "Reviewer-safe checks complete."

test-all: reviewer-test
