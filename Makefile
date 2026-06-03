.PHONY: reproduce preflight-v2 smoke-v2 smoke lint packet-validate reproduce-tables validate-locks validate-validation reviewer-test internal-test test-all help

PYTHON ?= python
PYTHONPATH := code/src

help:
	@echo "Targets: reproduce, reproduce-tables, validate-locks, validate-validation, reviewer-test, preflight-v2, smoke-v2"

preflight-v2:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) code/scripts/preflight_phase4_v2.py --mode smoke --agent-type scripted

smoke: smoke-v2

smoke-v2:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) code/scripts/run_phase4_v2.py --mode smoke --agent-type scripted --run-id reviewer_smoke --output-root runs --overwrite --disable-hf-backup

reproduce: preflight-v2 smoke-v2
	@echo "Reviewer smoke reproduction complete."

lint:
	$(PYTHON) -m ruff check code

packet-validate:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) code/scripts/build_final_supported_packet.py

reproduce-tables: packet-validate

validate-locks:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) code/scripts/validate_locked_scoring_targets.py

validate-validation:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) code/scripts/validate_validation_artifacts.py

reviewer-test: lint reproduce-tables validate-locks validate-validation preflight-v2
	@echo "Reviewer-safe checks complete."

test-all: reviewer-test

internal-test:
	@echo "Historical internal pytest tests require non-public fixture roots and are not part of this public reviewer bundle."
	@echo "Use 'make reviewer-test' for public clean-clone verification."
