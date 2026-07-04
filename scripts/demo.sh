#!/usr/bin/env bash
# End-to-end demo of the memory lifecycle — designed for screen recording.
# Prints clean output (Cognee's internal logs are filtered out).
#
# Usage: scripts/demo.sh        (straight through)
#        PAUSE=1 scripts/demo.sh (pause between steps — press Enter to advance)
set -uo pipefail

MNEMO="${MNEMO:-.venv/bin/mnemo}"
NOISE='2026-[0-9]|log_file|Logging init|Database storage|cognee_version=|Cognee 1.0 changes|auth posture|HF_TOKEN|Fetching|Warning: You are sending|it/s\]|00:0|alembic|migration|schema|plugin|Context impl|stamp|Using database|registered|Vector adapter|Migrated|Fresh database|namespace_|Edge|DDL'

step() { echo; echo "════════════════════════════════════════════════════════"; echo "▶ $1"; echo "════════════════════════════════════════════════════════"; [ "${PAUSE:-0}" = "1" ] && read -r -p "  (press Enter)…" _ || true; }
run()  { echo "\$ $*"; "$@" 2>&1 | grep -vE "$NOISE" | grep -v '^[[:space:]]*$'; }

step "Reset — start from a blank memory"
rm -rf .mnemo && echo "cleared ./.mnemo"

step "SESSION 1 — teach it a decision + ingest the codebase"
run "$MNEMO" remember "We use JWT in httpOnly cookies, not localStorage, after an XSS token-theft bug in the old version."
run "$MNEMO" ingest src/mnemo

step "Pretend we closed the terminal and opened a NEW session (no in-session state)"
echo "…new shell, zero context…"

step "SESSION 2 — it remembers across sessions"
run "$MNEMO" ask "how do we store auth tokens and why?"
run "$MNEMO" ask "what does the MemoryBackend protocol define?"

step "It gets smarter — consolidate (Cognee improve/memify)"
run "$MNEMO" consolidate

step "It forgets on cue — wipe everything"
run "$MNEMO" forget --all <<<"y"

step "Proof it forgot — the same question now returns nothing"
run "$MNEMO" ask "how do we store auth tokens and why?"

echo; echo "✓ Demo complete — remember · recall · improve · forget, all local, no API keys."
