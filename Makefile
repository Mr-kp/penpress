.PHONY: setup gate gate-fast briefing state journal evidence-new test

PY ?= uv run python

setup:
	uv sync

briefing:
	@$(PY) scripts/briefing.py

state:
	@$(PY) scripts/state.py

journal:
	@$(PY) scripts/journal.py "$(MSG)" "$(CARD)"

evidence-new:
	@$(PY) scripts/journal.py --evidence-new "$(CARD)"

gate:
	@$(PY) scripts/gate.py

gate-fast:
	@$(PY) scripts/gate.py --fast

test:
	@uv run pytest -q
