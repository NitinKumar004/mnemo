#!/usr/bin/env bash
# Seed a few realistic architectural decisions into mnemo's memory.
# Usage: scripts/seed.sh   (run from the project root, venv active or not)
set -euo pipefail

MNEMO="${MNEMO:-.venv/bin/mnemo}"

DECISIONS=(
  "We store auth tokens as JWTs in httpOnly cookies, never in localStorage, because we were hit by an XSS token-theft bug in the old version."
  "The memory engine is behind a MemoryBackend Protocol so we can swap Cognee for another engine without touching the CLI or service layer."
  "All Cognee state lives under ./.mnemo so the project is self-contained and a demo can be reset with a single rm -rf."
  "We use qwen2.5:7b via Ollama, not llama3.1:8b, because Cognee needs reliable structured JSON output for entity extraction."
)

for d in "${DECISIONS[@]}"; do
  echo "› remembering: ${d:0:70}..."
  "$MNEMO" remember "$d" >/dev/null 2>&1 && echo "  ✓"
done

echo "Seeded ${#DECISIONS[@]} decisions."
