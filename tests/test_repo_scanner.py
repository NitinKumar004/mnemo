"""Offline unit tests for the pure logic — no Cognee, no network, no API key."""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemo.ingest.repo_scanner import scan_repository
from mnemo.memory.base import MemoryBackend, RecallHit, RememberOutcome
from mnemo.service import MnemoService


def test_scan_filters_and_ignores(tmp_path: Path):
    (tmp_path / "app.py").write_text("print('hi')")
    (tmp_path / "README.md").write_text("# docs")
    (tmp_path / "photo.png").write_bytes(b"\x89PNG\r\n")  # binary — skipped
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "junk.js").write_text("noise")  # ignored dir — skipped

    rels = {f.rel_path for f in scan_repository(tmp_path)}
    assert rels == {"app.py", "README.md"}


def test_scan_hashes_are_content_addressed(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("one")
    first = scan_repository(tmp_path)[0].sha256
    f.write_text("two")
    second = scan_repository(tmp_path)[0].sha256
    assert first != second


class FakeBackend(MemoryBackend):
    """In-memory MemoryBackend so the service can be tested without Cognee."""

    def __init__(self):
        self.stored: dict[str, list[str]] = {}
        self.consolidated: list[str] = []
        self.forgotten: list[str] = []
        self.forgotten_ids: list[str] = []
        self._counter = 0

    async def remember(self, data, *, dataset, self_improve=False):
        self.stored.setdefault(dataset, []).append(str(data))
        self._counter += 1
        return RememberOutcome(
            status="completed",
            dataset=dataset,
            items=1,
            detail={"data_id": f"id-{self._counter}"},
        )

    async def recall(self, query, *, top_k=15):
        return [RecallHit(content=f"answer to: {query}", source="graph")]

    async def consolidate(self, *, dataset=None):
        self.consolidated.append(dataset or "main_dataset")

    async def forget(self, *, dataset=None, data_id=None, everything=False, memory_only=False):
        if data_id:
            self.forgotten_ids.append(data_id)
        else:
            self.forgotten.append("*" if everything else (dataset or ""))


async def test_sync_plan_detects_added_changed_removed(tmp_path: Path):
    svc = MnemoService(FakeBackend())
    (tmp_path / "a.py").write_text("v1")
    await svc.ingest_repository(tmp_path)

    (tmp_path / "a.py").write_text("v2")   # changed
    (tmp_path / "b.py").write_text("new")  # added

    plan = svc.plan_sync(tmp_path)
    assert {f.rel_path for f in plan.changed} == {"a.py"}
    assert {f.rel_path for f in plan.added} == {"b.py"}
    assert plan.removed == []


async def test_ask_delegates_to_backend(tmp_path: Path):
    backend = FakeBackend()
    svc = MnemoService(backend)
    hits = await svc.ask("how does auth work?")
    assert hits[0].content == "answer to: how does auth work?"


async def test_sync_forgets_deleted_file_precisely(tmp_path: Path, monkeypatch):
    # Point the manifest at a temp location so the test is hermetic.
    import mnemo.service as svc_mod

    monkeypatch.setattr(svc_mod, "MANIFEST_PATH", tmp_path / "manifest.json")

    backend = FakeBackend()
    svc = MnemoService(backend)

    (tmp_path / "keep.py").write_text("keep")
    (tmp_path / "gone.py").write_text("gone")
    await svc.ingest_repository(tmp_path)  # gone.py -> id-1 or id-2

    gone_id = svc._read_manifest()["gone.py"]["data_id"]
    (tmp_path / "gone.py").unlink()

    plan = svc.plan_sync(tmp_path)
    assert plan.removed == ["gone.py"]

    await svc.apply_sync(tmp_path, plan)

    # Forgotten precisely by data_id — not a whole-dataset rebuild.
    assert backend.forgotten_ids == [gone_id]
    assert backend.forgotten == []  # no dataset-level wipe
    assert "gone.py" not in svc._read_manifest()
    assert "keep.py" in svc._read_manifest()
