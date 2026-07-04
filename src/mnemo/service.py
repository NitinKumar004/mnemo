"""Orchestration layer.

Coordinates the memory backend with a local manifest so `ingest` and `sync`
behave incrementally. Contains no Cognee imports — it depends only on the
`MemoryBackend` port, so it's fully testable with a fake backend.

Manifest format: ``{rel_path: {"sha256": str, "data_id": str | None}}``.
The ``data_id`` lets `sync` forget an individual file precisely instead of
rebuilding the whole dataset.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .config import DATASET_CODE, DATASET_DECISIONS, STATE_DIR
from .ingest.repo_scanner import ScannedFile, scan_repository
from .memory.base import MemoryBackend, RecallHit

MANIFEST_PATH = STATE_DIR / "manifest.json"


@dataclass
class SyncPlan:
    """The diff between what's on disk and what's remembered."""

    added: list[ScannedFile]
    changed: list[ScannedFile]
    removed: list[str]  # rel_paths no longer present

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.changed or self.removed)


class MnemoService:
    """Business logic tying the CLI to a MemoryBackend."""

    def __init__(self, backend: MemoryBackend):
        self.backend = backend

    # ── decisions ─────────────────────────────────────────────────────────
    async def remember_decision(self, text: str):
        return await self.backend.remember(text, dataset=DATASET_DECISIONS)

    # ── code ingestion ────────────────────────────────────────────────────
    async def ingest_repository(self, root: Path) -> int:
        """Remember every source file under `root`; record it in the manifest."""
        manifest: dict[str, dict] = {}
        for f in scan_repository(root):
            outcome = await self.backend.remember(str(f.path), dataset=DATASET_CODE)
            manifest[f.rel_path] = {
                "sha256": f.sha256,
                "data_id": outcome.detail.get("data_id"),
            }
        self._write_manifest(manifest)
        return len(manifest)

    def plan_sync(self, root: Path) -> SyncPlan:
        """Compute what changed since the last ingest/sync (no side effects)."""
        current = {f.rel_path: f for f in scan_repository(root)}
        previous = self._read_manifest()

        added = [f for rel, f in current.items() if rel not in previous]
        changed = [
            f
            for rel, f in current.items()
            if rel in previous and _entry_sha(previous[rel]) != f.sha256
        ]
        removed = [rel for rel in previous if rel not in current]
        return SyncPlan(added=added, changed=changed, removed=removed)

    async def apply_sync(self, root: Path, plan: SyncPlan) -> None:
        """Reconcile memory with disk, forgetting individual files precisely.

        For removed and changed files we forget the exact stored item by its
        `data_id`; then we (re-)remember added and changed files. If any
        affected file predates data_id tracking (older manifest), we fall back
        to a full rebuild of the `code` dataset — always correct, just slower.
        """
        previous = self._read_manifest()

        forget_ids: list[str] = []
        missing_id = False
        for rel in [*plan.removed, *(f.rel_path for f in plan.changed)]:
            did = (previous.get(rel) or {}).get("data_id")
            if did:
                forget_ids.append(did)
            else:
                missing_id = True

        if missing_id:
            await self._rebuild_code_dataset(root)
            return

        for data_id in forget_ids:
            await self.backend.forget(
                dataset=DATASET_CODE, data_id=data_id, memory_only=True
            )

        manifest = dict(previous)
        for rel in plan.removed:
            manifest.pop(rel, None)
        for f in [*plan.added, *plan.changed]:
            outcome = await self.backend.remember(str(f.path), dataset=DATASET_CODE)
            manifest[f.rel_path] = {
                "sha256": f.sha256,
                "data_id": outcome.detail.get("data_id"),
            }
        self._write_manifest(manifest)

    async def _rebuild_code_dataset(self, root: Path) -> None:
        await self.backend.forget(dataset=DATASET_CODE, memory_only=True)
        manifest: dict[str, dict] = {}
        for f in scan_repository(root):
            outcome = await self.backend.remember(str(f.path), dataset=DATASET_CODE)
            manifest[f.rel_path] = {
                "sha256": f.sha256,
                "data_id": outcome.detail.get("data_id"),
            }
        self._write_manifest(manifest)

    # ── query / lifecycle ─────────────────────────────────────────────────
    async def ask(self, question: str, *, top_k: int = 15) -> list[RecallHit]:
        return await self.backend.recall(question, top_k=top_k)

    async def consolidate(self) -> None:
        for dataset in (DATASET_CODE, DATASET_DECISIONS):
            await self.backend.consolidate(dataset=dataset)

    async def forget_all(self) -> None:
        await self.backend.forget(everything=True)
        MANIFEST_PATH.unlink(missing_ok=True)

    async def forget_dataset(self, dataset: str) -> None:
        await self.backend.forget(dataset=dataset)
        if dataset == DATASET_CODE:
            MANIFEST_PATH.unlink(missing_ok=True)

    # ── manifest I/O ──────────────────────────────────────────────────────
    def manifest_stats(self) -> dict[str, int]:
        return {"tracked_files": len(self._read_manifest())}

    def _read_manifest(self) -> dict[str, dict]:
        if not MANIFEST_PATH.exists():
            return {}
        try:
            return json.loads(MANIFEST_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_manifest(self, mapping: dict[str, dict]) -> None:
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(json.dumps(mapping, indent=2, sort_keys=True))


def _entry_sha(entry: dict | str) -> str:
    """Read the sha256 from a manifest entry, tolerating the legacy str form."""
    if isinstance(entry, str):  # pre-data_id manifests stored the hash directly
        return entry
    return entry.get("sha256", "")
