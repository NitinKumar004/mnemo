"""The memory PORT.

Everything above this line (service, CLI) depends only on `MemoryBackend`,
never on Cognee. That keeps the memory engine swappable and lets tests run
against an in-memory fake with no network or API key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class RecallHit:
    """One piece of context returned from a query."""

    content: str
    source: str  # "graph" | "graph_context" | "session" | "trace" | ...
    score: float | None = None


@dataclass
class RememberOutcome:
    """Summary of a store operation."""

    status: str
    dataset: str
    items: int = 0
    detail: dict = field(default_factory=dict)


@runtime_checkable
class MemoryBackend(Protocol):
    """A pluggable long-term memory engine.

    The four methods map 1:1 to the memory lifecycle:
    remember → recall → consolidate(improve) → forget.
    """

    async def remember(
        self,
        data: str | list[str],
        *,
        dataset: str,
        self_improve: bool = False,
    ) -> RememberOutcome:
        """Store text or file paths in the given dataset."""
        ...

    async def recall(self, query: str, *, top_k: int = 15) -> list[RecallHit]:
        """Retrieve relevant context for a natural-language query."""
        ...

    async def consolidate(self, *, dataset: str | None = None) -> None:
        """Refine the graph: strengthen frequent links, prune stale nodes."""
        ...

    async def forget(
        self,
        *,
        dataset: str | None = None,
        data_id: str | None = None,
        everything: bool = False,
        memory_only: bool = False,
    ) -> None:
        """Delete memory — everything, a whole dataset, or one item by id."""
        ...
