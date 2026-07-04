# mnemo — the anti-amnesia coding companion

> AI coding assistants forget everything the moment the session ends. **mnemo**
> gives your project a persistent, self-hosted memory: it remembers your
> architectural decisions and code, recalls them across sessions, improves the
> more you use it, and forgets what you delete.
>
> Built for **The Hangover Part AI: Where's My Context?** hackathon — Cognee is
> central, and all four memory-lifecycle APIs are first-class commands.

## Why this exists

A stateless LLM re-reads your code cold every session and re-suggests things you
already rejected. mnemo puts a **knowledge graph** between you and the amnesia:

- `remember` — store a decision ("JWT in httpOnly cookies, not localStorage —
  we got hit by an XSS token theft") or ingest your source files.
- `recall` — ask "how does auth work here and why?" in a brand-new session and
  get an answer grounded in what you told it before.
- `consolidate` (Cognee's `improve`/memify) — strengthen frequently-referenced
  patterns, prune stale ones. Memory that gets *smarter* with use.
- `forget` — delete memory for a module you removed, or wipe everything.

## Tech stack

| Concern | Choice |
|---|---|
| Memory engine | **Cognee** (knowledge graph + vector + relational) |
| Reasoning LLM | **Ollama** (`qwen2.5:7b`) via Cognee → litellm — runs on your machine |
| Embeddings | **fastembed** (`all-MiniLM-L6-v2`, 384-dim), local & on-device |
| CLI | **Typer** · **Rich** |
| Packaging | hatchling, `src/` layout, Python 3.10–3.13 |

**Zero external dependencies.** LLM, embeddings, and all databases run locally;
nothing leaves your machine, no API keys. (Swap in Claude/Gemini via `.env` if
you'd rather use a cloud model — see `.env.example`.)

## Architecture — ports & adapters

The CLI never touches Cognee directly. It depends on a `MemoryBackend` *port*;
Cognee is one *adapter*. Swap the engine or mock it for tests without touching
anything above.

```
CLI (Typer)  ─►  MnemoService  ─►  MemoryBackend (Protocol)  ─►  CogneeBackend ─► Cognee
 thin           manifest/sync       the abstraction              the only file      Claude + fastembed
 commands       pure logic          (also: FakeBackend in tests) that imports cognee  Ladybug · LanceDB · SQLite
```

```
src/mnemo/
├── config.py               # load .env → configure Cognee (Claude + fastembed)
├── console.py              # Rich output helpers
├── memory/
│   ├── base.py             # PORT: MemoryBackend Protocol + RecallHit/RememberOutcome
│   └── cognee_backend.py   # ADAPTER: the only module that imports cognee
├── ingest/repo_scanner.py  # walk repo, ignore noise, content-hash files
├── service.py              # manifest + ingest + sync orchestration (no cognee import)
└── cli.py                  # remember · ingest · ask · consolidate · sync · forget · status
```

Why it's extensible: the memory engine is behind one interface, the sync/
scanning logic is pure and unit-tested offline, and the CLI is a thin shell.

## How we built it (design decisions)

A short, honest account of the choices behind the code:

1. **Memory behind an interface, not a hard dependency.** The very first thing
   we wrote was the `MemoryBackend` Protocol — *before* touching Cognee. The CLI
   and service talk to that interface; `CogneeBackend` is the single file that
   imports Cognee. This kept the design honest: the tool is "a memory-lifecycle
   app that happens to run on Cognee," not "a Cognee script." It also means the
   whole test suite runs offline against a `FakeBackend`.

2. **Local-first, because the theme is self-hosted memory.** We deliberately
   put both the LLM (Ollama) and embeddings (fastembed) on-device, so the tool
   has *zero* external dependencies and no API keys. Cloud models (Claude,
   Gemini) are a one-line `.env` swap — the code never changes.

3. **`qwen2.5:7b`, not `llama3.1:8b`.** Our first local run *worked* but
   `llama3.1:8b` kept violating Cognee's structured-output schema during
   summarization (returning a dict where a string was expected). Switching to
   `qwen2.5:7b`, which is much stronger at JSON/structured output, fixed it
   cleanly. Lesson: with Cognee, the model's structured-output reliability
   matters more than raw size.

4. **Recall must be grounded in memory.** Early on, asking a question *after*
   `forget` still produced an answer — the LLM was replying from its own general
   knowledge, making `forget` look broken. We fixed `recall` to first fetch the
   retrieved *context*; if nothing is in memory, we return nothing. Now `forget`
   visibly works, which is the whole point of the demo.

5. **Precise forget over rebuild.** `sync` records each file's Cognee `data_id`
   in a manifest, so deleting a file forgets *exactly* that file's memory rather
   than rebuilding the dataset. We kept a full-rebuild fallback for older
   manifests — correct always, fast in the common case.

6. **Config gotchas we hit (documented so you don't):** Cognee needs *absolute*
   data paths; it re-reads `.env` with `override=True` at import (so relative
   path overrides get clobbered — we set them in code instead); and it requires
   `EMBEDDING_DIMENSIONS` when you pick a custom embedder (`384` for MiniLM).

## Setup

Requires Python 3.10–3.13. No API key — the default stack is fully local.

```bash
# 1. Local LLM via Ollama
brew install ollama
ollama serve &                 # start the server (or: brew services start ollama)
ollama pull qwen2.5:7b         # ~4.7GB; strong at the structured output Cognee needs

# 2. The tool
git clone <your-repo> && cd coding-companion
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env           # already set for local Ollama + fastembed

# 3. Verify
pytest                         # offline sanity check
```

Config lives in `.env` (see `.env.example`). Everything runs locally:
`qwen2.5:7b` for reasoning, `fastembed` for embeddings. Pick the embedder
**before** your first `ingest` — switching it later changes vector
dimensionality and requires `mnemo forget --all` + re-ingest.

> **Model note:** use `qwen2.5:7b`, not `llama3.1:8b` — Cognee relies on
> structured (JSON-schema) output for entity extraction and summarization, and
> the llama 8B model fails that schema. `qwen2.5:7b` handles it cleanly.

## Usage

```bash
mnemo remember "We use JWT in httpOnly cookies, not localStorage, after an XSS token-theft bug."
mnemo ingest .                     # build codebase memory from source files
mnemo ask "how does auth work here and why?"
mnemo consolidate                  # self-improve the graph
mnemo sync .                       # reconcile after edits/deletions
mnemo forget --dataset code        # or --all
mnemo status
```

## The demo (what to record)

1. **Session 1 — teach it.** `mnemo remember "…XSS decision…"`, then `mnemo ingest .`.
2. **Close the terminal. Open a fresh one.** (Prove there's no in-session state.)
3. **Session 2 — it remembers.** `mnemo ask "how does auth work and why?"` →
   answer cites the XSS decision.
4. **It gets smarter.** `mnemo consolidate`.
5. **It forgets on cue.** Delete a file, `mnemo sync .` → its memory disappears.

Narrative: *"Every coding AI forgets your project the second you close it. Mine
remembers a security decision from a previous session, gets smarter when I
consolidate, and correctly forgets a module I deleted. This is where the context
went."*

## Testing

```bash
pytest           # runs fully offline against an in-memory FakeBackend
```

## Extending

- **New memory engine:** implement `MemoryBackend` (see `memory/base.py`) and
  point the CLI at it. Nothing else changes.
- **Precise per-file forget:** `sync` currently rebuilds the `code` dataset when
  files are deleted. To forget individual files, persist each file's Cognee
  `data_id` in the manifest and call `forget(dataset=…, data_id=…)`.
- **More sources:** add a loader (issues, PRs, docs) that produces text and call
  `service.remember_decision` / a new dataset.
