"""Rich console helpers — keeps presentation out of the CLI logic."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .memory.base import RecallHit

console = Console()


def info(msg: str) -> None:
    console.print(f"[cyan]›[/cyan] {msg}")


def success(msg: str) -> None:
    console.print(f"[green]✓[/green] {msg}")


def warn(msg: str) -> None:
    console.print(f"[yellow]![/yellow] {msg}")


def error(msg: str) -> None:
    console.print(f"[red]✗[/red] {msg}")


def render_answer(question: str, hits: list[RecallHit]) -> None:
    """Show a recalled answer plus its supporting context."""
    if not hits:
        warn("Nothing in memory matched that question yet.")
        return

    # The first, highest-signal hit reads as the answer; the rest is context.
    console.print(Panel(hits[0].content, title=f"[bold]Q:[/bold] {question}", border_style="green"))

    if len(hits) > 1:
        table = Table(title="Supporting context", show_lines=False, expand=True)
        table.add_column("source", style="dim", no_wrap=True)
        table.add_column("content")
        for h in hits[1:6]:
            snippet = h.content if len(h.content) < 300 else h.content[:297] + "…"
            table.add_row(h.source, snippet)
        console.print(table)
