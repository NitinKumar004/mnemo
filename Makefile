# mnemo — developer tasks
VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip
MNEMO := $(VENV)/bin/mnemo

.PHONY: help setup model test seed demo clean ollama-up

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup:  ## Create venv + install (Python 3.10–3.13)
	python3 -m venv $(VENV)
	$(PIP) install -q --upgrade pip
	$(PIP) install -e ".[dev]"
	@echo "✓ installed. Next: 'make model' (once), then 'make demo'."

model:  ## Pull the local LLM (qwen2.5:7b) via Ollama
	ollama pull qwen2.5:7b

ollama-up:  ## Start the Ollama server in the background
	@curl -s http://localhost:11434/api/tags >/dev/null 2>&1 && echo "Ollama already up" || \
	  (ollama serve > /tmp/ollama.log 2>&1 & echo "started Ollama (logs: /tmp/ollama.log)")

test:  ## Run the offline test suite
	$(VENV)/bin/pytest -q

seed:  ## Remember a few sample architectural decisions
	MNEMO=$(MNEMO) bash scripts/seed.sh

demo:  ## Run the full lifecycle demo (recordable). PAUSE=1 to step through.
	MNEMO=$(MNEMO) bash scripts/demo.sh

clean:  ## Delete all local memory state
	rm -rf .mnemo && echo "cleared ./.mnemo"
