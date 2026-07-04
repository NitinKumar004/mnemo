"""mnemo CLI — the anti-amnesia coding companion.

Thin command layer: parse args, bootstrap the Cognee-backed service, delegate,
and render. All real logic lives in `service.py` / `memory/`.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer

from . import __version__, console
from .config import (
    DATASET_CODE,
    DATASET_DECISIONS,
    ConfigError,
    configure_cognee,
    load_settings,
)
from .service import MnemoService

app = typer.Typer(
    add_completion=False,
    help="mnemo — persistent, self-hosted memory for your codebase (Cognee + Claude).",
)


def _service() -> MnemoService:
    """Bootstrap config → Cognee → service. Exits cleanly on config errors."""
    try:
        settings = load_settings()
    except ConfigError as exc:
        console.error(str(exc))
        raise typer.Exit(code=1)

    configure_cognee(settings)
    # Imported here so the heavy Cognee import happens only after configuration.
    from .memory.cognee_backend import CogneeBackend

    console.info(
        f"LLM: [bold]{settings.llm_model}[/bold] · "
        f"embeddings: [bold]{settings.embedding_provider}[/bold] "
        f"({'local' if settings.uses_local_embeddings else 'remote'})"
    )
    return MnemoService(CogneeBackend())


def _run(coro):
    return asyncio.run(coro)


@app.command()
def version():
    """Print the mnemo version."""
    console.console.print(f"mnemo {__version__}")


@app.command()
def remember(
    text: str = typer.Argument(..., help="A decision, rationale, or fact to store."),
):
    """Store an architectural decision or 'why we did X' in memory."""
    svc = _service()
    with console.console.status("Remembering…"):
        _run(svc.remember_decision(text))
    console.success(f"Stored in '{DATASET_DECISIONS}'.")


@app.command()
def ingest(
    path: Path = typer.Argument(Path("."), help="Repository root to ingest."),
):
    """Scan a repo and build codebase memory from its source files."""
    svc = _service()
    with console.console.status(f"Ingesting source files under {path}…"):
        count = _run(svc.ingest_repository(path))
    console.success(f"Ingested {count} files into '{DATASET_CODE}'.")


@app.command()
def ask(
    question: str = typer.Argument(..., help="A natural-language question."),
    top_k: int = typer.Option(15, help="How many context items to retrieve."),
):
    """Answer a question using the codebase memory + remembered decisions."""
    svc = _service()
    with console.console.status("Recalling…"):
        hits = _run(svc.ask(question, top_k=top_k))
    console.render_answer(question, hits)


@app.command()
def consolidate():
    """Self-improve the graph: strengthen frequent links, prune stale nodes."""
    svc = _service()
    with console.console.status("Consolidating memory (improve)…"):
        _run(svc.consolidate())
    console.success("Memory consolidated.")


@app.command()
def sync(
    path: Path = typer.Argument(Path("."), help="Repository root to reconcile."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Apply without confirmation."),
):
    """Reconcile memory with the current files (remember new/changed, forget deleted)."""
    svc = _service()
    plan = svc.plan_sync(path)

    if plan.is_empty:
        console.success("Memory is already in sync with the repository.")
        return

    console.info(
        f"Plan: [green]+{len(plan.added)} added[/green], "
        f"[yellow]~{len(plan.changed)} changed[/yellow], "
        f"[red]-{len(plan.removed)} removed[/red]."
    )
    for rel in plan.removed:
        console.console.print(f"   [red]- {rel}[/red]")

    if not yes and not typer.confirm("Apply this sync?"):
        console.warn("Aborted.")
        raise typer.Exit(code=0)

    with console.console.status("Applying sync…"):
        _run(svc.apply_sync(path, plan))
    console.success("Sync complete.")


@app.command()
def forget(
    all_: bool = typer.Option(False, "--all", help="Forget everything mnemo stored."),
    dataset: Optional[str] = typer.Option(
        None, "--dataset", help=f"Forget one dataset: '{DATASET_CODE}' or '{DATASET_DECISIONS}'."
    ),
):
    """Delete memory — a single dataset, or everything."""
    svc = _service()
    if all_:
        if not typer.confirm("Forget ALL mnemo memory? This cannot be undone."):
            raise typer.Exit(code=0)
        with console.console.status("Forgetting everything…"):
            _run(svc.forget_all())
        console.success("All memory forgotten.")
    elif dataset:
        with console.console.status(f"Forgetting '{dataset}'…"):
            _run(svc.forget_dataset(dataset))
        console.success(f"Dataset '{dataset}' forgotten.")
    else:
        console.error("Specify --all or --dataset <name>.")
        raise typer.Exit(code=1)


@app.command()
def status():
    """Show what's tracked in memory and the active configuration."""
    svc = _service()
    stats = svc.manifest_stats()
    console.success(f"Tracked source files: {stats['tracked_files']}")


if __name__ == "__main__":
    app()
