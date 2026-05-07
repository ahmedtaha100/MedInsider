.PHONY: reproduce preflight-v2 smoke-v2 smoke test-all help

PYTHON ?= python
PYTHONPATH := code/src

help:
	@echo "Targets: reproduce, preflight-v2, smoke-v2, test-all"

preflight-v2:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) code/scripts/preflight_phase4_v2.py --mode smoke --agent-type scripted

smoke: smoke-v2

smoke-v2:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) code/scripts/run_phase4_v2.py --mode smoke --agent-type scripted --run-id reviewer_smoke --output-root runs --overwrite --disable-hf-backup

reproduce: preflight-v2 smoke-v2
	@echo "Reviewer smoke reproduction complete."

test-all:
	PYTHONPATH=$(PYTHONPATH):code $(PYTHON) -m pytest code/tests -v
