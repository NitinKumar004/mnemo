"""The Cognee ADAPTER.

Implements `MemoryBackend` by delegating to Cognee's v2 lifecycle API:
`remember`, `recall`, `improve`, `forget`. This is the *only* module in the
project that imports Cognee — swap it out to run on a different memory engine.
"""

from __future__ import annotations

from .base import MemoryBackend, RecallHit, RememberOutcome


class CogneeBackend(MemoryBackend):
    """MemoryBackend backed by Cognee (Claude + local fastembed)."""

    async def remember(
        self,
        data: str | list[str],
        *,
        dataset: str,
        self_improve: bool = False,
    ) -> RememberOutcome:
        import cognee

        # self_improve=False here because we run `improve()` explicitly via the
        # `consolidate` command — avoids paying that cost on every file.
        result = await cognee.remember(
            data,
            dataset_name=dataset,
            self_improvement=self_improve,
        )
        # Capture the data_id of the item we just stored, so `sync` can later
        # forget exactly this file (not rebuild the whole dataset).
        data_id = await self._last_data_id(getattr(result, "dataset_id", None))
        return RememberOutcome(
            status=getattr(result, "status", "completed"),
            dataset=dataset,
            items=getattr(result, "items_processed", 0),
            detail={"dataset_id": getattr(result, "dataset_id", None), "data_id": data_id},
        )

    @staticmethod
    async def _last_data_id(dataset_id: str | None) -> str | None:
        """Best-effort lookup of the most-recently-added Data id in a dataset."""
        if not dataset_id:
            return None
        try:
            from uuid import UUID

            from cognee.modules.data.methods import get_last_added_data

            data = await get_last_added_data(UUID(str(dataset_id)))
            return str(data.id) if data is not None else None
        except Exception:
            return None

    async def recall(self, query: str, *, top_k: int = 15) -> list[RecallHit]:
        import cognee

        # Step 1: fetch the retrieved *context* (no LLM answer). This tells us
        # whether anything is actually in memory. Without this gate, graph
        # completion would happily answer from the model's own general
        # knowledge even after everything has been forgotten — making `forget`
        # look broken. We answer only from what we truly remember.
        context = await cognee.recall(query, top_k=top_k, only_context=True)
        if not any(_content_text(c).strip() for c in context):
            return []

        # Step 2: memory has relevant content — produce a grounded answer.
        responses = await cognee.recall(query, top_k=top_k)
        hits: list[RecallHit] = []
        for r in responses:
            text = _content_text(r) or str(r)
            hits.append(
                RecallHit(
                    content=text,
                    source=getattr(r, "source", "graph"),
                    score=getattr(r, "score", None),
                )
            )
        return hits

    async def consolidate(self, *, dataset: str | None = None) -> None:
        import cognee

        await cognee.improve(dataset=dataset or "main_dataset")

    async def forget(
        self,
        *,
        dataset: str | None = None,
        data_id: str | None = None,
        everything: bool = False,
        memory_only: bool = False,
    ) -> None:
        import cognee

        if everything:
            await cognee.forget(everything=True)
        elif data_id and dataset:
            from uuid import UUID

            await cognee.forget(
                dataset=dataset, data_id=UUID(data_id), memory_only=memory_only
            )
        elif dataset:
            await cognee.forget(dataset=dataset, memory_only=memory_only)
        else:
            raise ValueError("forget requires `dataset`, `data_id`+`dataset`, or `everything`")


def _content_text(response: object) -> str:
    """Return the *real* text content of a recall item, or "" if there is none.

    Deliberately does NOT fall back to repr() — callers use the emptiness of
    this value to decide whether memory actually contains anything. Cognee
    returns a discriminated union (graph completion, graph context, session QA,
    trace); we read the known text-bearing fields only.
    """
    for attr in ("content", "text", "answer", "value"):
        val = getattr(response, attr, None)
        if isinstance(val, str) and val.strip():
            return val
    return ""
