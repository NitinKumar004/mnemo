"""Walk a repository and pick out the source files worth remembering.

Pure, dependency-free logic so it's trivially unit-testable. Applies a set of
sensible ignore rules (build dirs, VCS, binaries) and filters to known source
extensions. Content-hashes each file so the service layer can diff against a
manifest and drive incremental sync.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

# Directories we never want in memory.
IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".git", ".hg", ".svn",
        ".mnemo",                     # our own state
        ".venv", "venv", "env",
        "node_modules", "dist", "build", "target", "out",
        "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        ".idea", ".vscode",
    }
)

# Source-ish extensions worth extracting a graph from.
SOURCE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt",
        ".rb", ".php", ".c", ".h", ".cpp", ".hpp", ".cs", ".swift", ".scala",
        ".sql", ".sh", ".yaml", ".yml", ".toml", ".md", ".rst",
    }
)

# Skip files larger than this (bytes) — usually generated/minified.
MAX_FILE_BYTES = 256 * 1024


@dataclass(frozen=True)
class ScannedFile:
    """A source file selected for ingestion."""

    path: Path          # absolute path on disk
    rel_path: str       # path relative to the repo root (manifest key)
    sha256: str         # content hash


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scan_repository(root: Path) -> list[ScannedFile]:
    """Return the source files under `root`, ignoring noise dirs and binaries."""
    root = root.resolve()
    results: list[ScannedFile] = []

    for path in _walk(root):
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            data = path.read_bytes()
        except (OSError, PermissionError):
            continue

        results.append(
            ScannedFile(
                path=path,
                rel_path=str(path.relative_to(root)),
                sha256=_hash_bytes(data),
            )
        )

    results.sort(key=lambda f: f.rel_path)  # deterministic ordering
    return results


def _walk(root: Path):
    """Yield files under root, pruning ignored directories as we descend."""
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except (OSError, PermissionError):
            continue
        for entry in entries:
            if entry.is_dir():
                if entry.name in IGNORED_DIRS or entry.name.startswith("."):
                    continue
                stack.append(entry)
            elif entry.is_file():
                yield entry
