# mnemo — Submission

**Hackathon:** The Hangover Part AI: *Where's My Context?* (WeMakeDevs × Cognee)
**Track:** Open-source Cognee (100% self-hosted, no cloud)
**One line:** An anti-amnesia coding companion — persistent, self-hosted memory
for your codebase that remembers decisions across sessions, gets smarter over
time, and forgets what you delete.

## The problem

Every AI coding assistant forgets your project the moment the session ends. Ask
it "why is auth done this way?" tomorrow and it re-reads the code cold, with no
memory of the decisions, the bugs, or the reasoning. That's the "AI amnesia"
this hackathon is about.

## What mnemo does

A CLI that gives a codebase a persistent brain, built on **Cognee's knowledge
graph**. It exposes Cognee's memory lifecycle directly as commands:

| Command | Lifecycle API | What it does |
|---|---|---|
| `mnemo remember "<decision>"` | `cognee.remember` | Store a decision / "why we did X" |
| `mnemo ingest <path>` | `cognee.remember` (per file) | Build a graph from source files |
| `mnemo ask "<question>"` | `cognee.recall` | Answer, grounded strictly in memory |
| `mnemo consolidate` | `cognee.improve` (memify) | Strengthen/prune the graph — self-improve |
| `mnemo sync <path>` | `cognee.remember` + `cognee.forget` | Reconcile memory with the repo |
| `mnemo forget [--all/--dataset]` | `cognee.forget` | Controlled deletion |

**All four lifecycle verbs (remember · recall · improve · forget) are
first-class, user-visible features** — not just remember+recall.

## How Cognee is central

Cognee *is* the product. mnemo is a thin, well-structured shell around Cognee's
memory engine:

- `remember` runs Cognee's `add → cognify` pipeline: an LLM extracts entities
  and relationships and commits them to the **knowledge graph** (Ladybug) +
  **vector store** (LanceDB).
- `ask` uses Cognee's auto-routed `recall` (graph traversal + completion), so
  answers connect a question to related decisions through graph edges — not
  keyword matching. We gate on retrieved context so answers are grounded in
  memory, and `forget` visibly zeroes them out.
- `consolidate` calls Cognee's `improve`/memify — the self-improvement step.
- `sync` uses Cognee's `forget(data_id=…)` to precisely drop a deleted file's
  memory, tracked via a local manifest of `rel_path → data_id`.

## 100% local & self-hosted

Nothing leaves the machine, no API keys:

- **LLM:** Ollama (`qwen2.5:7b`) — local inference.
- **Embeddings:** fastembed (`all-MiniLM-L6-v2`, 384-dim) — on-device.
- **Databases:** Ladybug + LanceDB + SQLite, all under `./.mnemo/`.

(Swap in Claude or Gemini via `.env` for higher-quality output — one line, no
code change, thanks to the backend abstraction.)

## Architecture (why it's extensible)

Ports & adapters: the CLI and service depend on a `MemoryBackend` **Protocol**,
never on Cognee directly. `CogneeBackend` is the one adapter that imports
Cognee; tests run against an in-memory `FakeBackend` with no network. Swapping
the memory engine is one new class.

```
CLI (Typer) → MnemoService (manifest/sync) → MemoryBackend (port) → CogneeBackend → Cognee
```

## Run it

```bash
brew install ollama && ollama serve &
ollama pull qwen2.5:7b
make setup            # venv + install
make test             # offline tests
make demo             # full lifecycle demo (PAUSE=1 to step through)
```

## Demo narrative

Teach it a security decision + ingest the code → **close the terminal, open a
new one** → it answers "how does auth work and why?" citing the decision →
`consolidate` to self-improve → delete a file and `sync`, or `forget --all`, and
the same question returns *"Nothing in memory matched."* That's where the
context went.

## AI assistance disclosure

Built with the help of Claude (Claude Code) for scaffolding, wiring the Cognee
lifecycle APIs, and debugging the local Ollama + fastembed configuration.
