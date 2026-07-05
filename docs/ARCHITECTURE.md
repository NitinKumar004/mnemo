# How mnemo works

**In one line:** mnemo gives your codebase a memory that survives across sessions —
so your AI assistant stops forgetting *why* your code is the way it is.

This doc has two parts:
- **Part 1 — In plain English.** No jargon. Read this if you just want to *get it*.
- **Part 2 — For engineers.** The components, the data flow, and the design choices.

---

# Part 1 — In plain English

## The problem, with an analogy

Imagine hiring a brilliant contractor who has **no long-term memory**. Every morning
they show up sharp and capable — but they've forgotten everything from yesterday.
You explained *why* the login uses cookies instead of browser storage? Gone. You'll
explain it again today. And tomorrow.

That's exactly how today's AI coding assistants work. They're smart in the moment,
but the instant you close the session, the context is wiped. This is often called
**"AI amnesia."**

## What mnemo does

mnemo is a small command-line tool that gives that contractor a **notebook they
actually keep** — a permanent, searchable memory of your project.

- You **tell it a decision** ("we store login tokens in cookies, not browser storage,
  because we got hacked that way once"), or point it at your code.
- Later — even in a brand-new session — you **ask a question** and it *remembers*,
  and can explain the reasoning.
- When something is no longer true, it **forgets** it.

## Why it's smarter than a simple search box

A basic search just matches words: search "auth" and you get things containing the
word "auth." mnemo is built on a tool called **Cognee**, which instead builds a
**mind-map** of your project — it understands that "login," "tokens," "cookies," and
"that old security bug" are all *connected*. So when you ask about one, it can pull in
the related reasoning, even if you never used the exact same words.

Think of it as the difference between:
- **A pile of sticky notes** you flip through looking for a keyword, versus
- **A mind-map on the wall** where related ideas are linked with string.

## A real-life story

> **Monday.** You tell mnemo: *"We use cookies for login tokens, not browser storage,
> because we got hit by a security bug the old way."* mnemo files it away.
>
> **Tuesday.** New day, fresh session — the assistant "remembers nothing" on its own.
> But you ask mnemo: *"How do we handle login tokens, and why?"* It answers correctly,
> and explains the security reason you gave on Monday. **It remembered.**
>
> **Wednesday.** You delete an old part of the project. You run one command and mnemo
> **forgets** just that part's memory — nothing stale is left behind.

## Why it all runs on your own computer

mnemo runs **100% on your machine** — no cloud, no accounts, no API keys, and your
code never leaves your laptop. We chose this on purpose:

- **Privacy** — your source code and decisions stay with you.
- **Free** — nothing to pay for or sign up to.
- **Always works** — no internet or external service required.

You *can* switch it to use a cloud AI (like Claude or Gemini) by changing one line of
settings — but by default, everything is private and local.

---

# Part 2 — For engineers

## The stack

| Layer | Choice | Role |
|---|---|---|
| Memory engine | **Cognee** (open source) | knowledge graph + vector + relational store |
| Reasoning LLM | **Ollama** running `qwen2.5:7b` (local) | entity/relation extraction, summarization, answering |
| Embeddings | **fastembed** `all-MiniLM-L6-v2` (local, 384-dim) | turns text into vectors for semantic search |
| CLI / UX | **Typer** + **Rich** | commands and terminal output |
| Language | Python 3.10–3.13 | — |

**Zero external dependencies by default.** Cloud LLMs are a one-line `.env` swap.

## Two *different* kinds of model (the thing people miss)

The system needs two model types doing two unrelated jobs:

1. **A reasoning LLM (qwen2.5 via Ollama)** — the "thinker." During ingestion it reads
   text and extracts entities + relationships; during a query it composes the answer.
2. **An embedding model (fastembed)** — the "indexer." It converts text into a vector
   of numbers so similar meanings sit near each other. This powers semantic search.

They are **not interchangeable** — a chat LLM can't produce embeddings, and an embedder
can't reason. Cognee needs both. (If you configure only the LLM, Cognee silently
defaults embeddings to OpenAI and will demand a key — we set both explicitly to avoid
that trap.)

> **Why `qwen2.5:7b`, not `llama3.1:8b`?** Cognee requires the LLM to emit *structured
> JSON* (entities/relations against a schema). llama-3.1-8b repeatedly violated that
> schema; qwen2.5-7b handles structured output reliably. For Cognee, structured-output
> reliability matters more than raw model size.

## Three local databases (all under `./.mnemo/`)

Cognee writes the same knowledge into three stores, each answering a different question:

| Store | Default | Holds | Answers |
|---|---|---|---|
| Graph DB | Ladybug | entities + typed relationships | "what connects to what, and why" |
| Vector DB | LanceDB | embeddings of chunks/nodes | "what's semantically similar" |
| Relational DB | SQLite | datasets, data records, manifest lookups | state & bookkeeping |

The whole thing is self-contained and disposable — `rm -rf .mnemo` resets it.

## The memory lifecycle → Cognee APIs

| mnemo command | Cognee call | What happens |
|---|---|---|
| `remember` / `ingest` | `remember` (= `add` + `cognify`) | LLM extracts entities/relations → graph + vectors |
| `ask` | `recall` | vector search + graph traversal, then LLM composes an answer |
| `consolidate` | `improve` (memify) | strengthen frequent links, prune stale nodes |
| `forget` / `sync` | `forget` | precise (per-file) or whole-dataset deletion |

## Architecture: ports & adapters (hexagonal)

The CLI and orchestration layer never touch Cognee directly. They depend on an
**interface** (`MemoryBackend`); Cognee is one **adapter** behind it. This makes the
memory engine swappable and lets the whole test suite run offline against a fake.

```
CLI (Typer)                     thin: parse args, render output
    │  calls
    ▼
MnemoService                    orchestration: manifest, ingest, sync  (no cognee import)
    │  depends on the INTERFACE
    ▼
MemoryBackend  (Protocol)       remember · recall · consolidate · forget   ← the "port"
    │  implemented by
    ├────────────────────────────┐
    ▼                            ▼
CogneeBackend                 FakeBackend (tests)
 (the only file that           in-memory, no network, no key
  imports cognee)
    │
    ▼
Cognee  →  Ladybug (graph) · LanceDB (vectors) · SQLite (state)
        →  qwen2.5 via Ollama (reasoning) · fastembed (embeddings)
```

### Files

```
src/mnemo/
├── config.py               # load .env → configure Cognee (Ollama + fastembed); dataset names
├── console.py              # Rich output helpers
├── memory/
│   ├── base.py             # PORT: MemoryBackend Protocol + RecallHit / RememberOutcome
│   └── cognee_backend.py   # ADAPTER: the only module that imports cognee
├── ingest/repo_scanner.py  # pure logic: walk repo, ignore noise, content-hash files
├── service.py              # manifest + ingest + sync orchestration (no cognee import)
└── cli.py                  # remember · ingest · ask · consolidate · sync · forget · status
```

Two design details worth calling out:

- **Grounded recall.** `recall` first fetches the *retrieved context*; if memory is
  empty it returns nothing, instead of letting the LLM answer from its own general
  knowledge. This is what makes `forget` *visibly* work.
- **Precise forget.** On `remember`, we capture each file's Cognee `data_id` in a local
  manifest (`filepath → {sha256, data_id}`). `sync` then forgets an individual deleted
  file by its `data_id`, rather than rebuilding the whole dataset.

## End-to-end trace: `mnemo ask "how do we store auth tokens and why?"`

```
1. cli.py            parse args → _service() bootstraps config → CogneeBackend → MnemoService
2. service.py        MnemoService.ask(question)          (knows only the interface)
3. memory/base.py    MemoryBackend.recall(...)           (the port)
4. cognee_backend    cognee.recall(...)                  (the adapter)
5. Cognee:
     fastembed   →   embed the question (384-dim vector)      [local embedding model]
     LanceDB     →   find the most similar stored vectors     [vector store]
     Ladybug     →   traverse edges to related decisions      [graph store]
     qwen2.5     →   compose a grounded answer                [local reasoning LLM]
6. console.py        render the answer panel in the terminal
```

Because the arrows only point *down toward the interface*, swapping the memory engine
(or mocking it in tests) never touches the CLI or the service layer.

## Extending it

- **New memory engine:** implement `MemoryBackend` and point the CLI at it. Nothing else changes.
- **Cloud model:** change `LLM_PROVIDER` / `LLM_MODEL` in `.env` (e.g. Anthropic or Gemini).
- **New sources:** add a loader (issues, PRs, docs) that produces text and `remember` it.
