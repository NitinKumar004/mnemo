"""Configuration + Cognee bootstrap.

Loads ``.env`` and configures Cognee to use Claude for reasoning and a local
fastembed model for embeddings. Everything is pinned to a project-local
``.mnemo/`` directory so the whole thing is self-contained and disposable.

`import cognee` is intentionally deferred until *after* the environment is
prepared — Cognee reads a lot of settings at import time.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Dataset names. `code` holds ingested source files; `decisions` holds
# free-text notes ("why we did X"). recall() searches across both.
DATASET_CODE = "code"
DATASET_DECISIONS = "decisions"

# Where all local state lives (graph, vectors, sqlite, manifest).
STATE_DIR = Path(".mnemo")


@dataclass(frozen=True)
class Settings:
    """Resolved, validated configuration."""

    llm_provider: str
    llm_model: str
    llm_api_key: str
    llm_endpoint: str | None
    embedding_provider: str
    embedding_model: str
    data_root: str
    system_root: str

    @property
    def uses_local_embeddings(self) -> bool:
        return self.embedding_provider in {"fastembed", "ollama"}


class ConfigError(RuntimeError):
    """Raised when required configuration is missing."""


def load_settings() -> Settings:
    """Load `.env`, apply project-local defaults, and validate."""
    load_dotenv(override=False)

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Cognee requires ABSOLUTE paths. Resolve project-local dirs to absolute,
    # and normalise any relative override the user set in .env.
    abs_state = STATE_DIR.resolve()
    data_root = os.environ.get("DATA_ROOT_DIRECTORY") or str(abs_state / "data")
    system_root = os.environ.get("SYSTEM_ROOT_DIRECTORY") or str(abs_state / "system")
    os.environ["DATA_ROOT_DIRECTORY"] = str(Path(data_root).resolve())
    os.environ["SYSTEM_ROOT_DIRECTORY"] = str(Path(system_root).resolve())
    os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")
    os.environ.setdefault("TELEMETRY_DISABLED", "1")

    llm_provider = os.environ.get("LLM_PROVIDER", "anthropic")
    llm_model = os.environ.get("LLM_MODEL", "claude-opus-4-8")
    llm_api_key = os.environ.get("LLM_API_KEY", "")
    llm_endpoint = os.environ.get("LLM_ENDPOINT") or None
    embedding_provider = os.environ.get("EMBEDDING_PROVIDER", "fastembed")
    embedding_model = os.environ.get(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    if not llm_api_key:
        raise ConfigError(
            "LLM_API_KEY is not set. Copy .env.example to .env and add your "
            "Anthropic API key."
        )

    return Settings(
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
        llm_endpoint=llm_endpoint,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        data_root=os.environ["DATA_ROOT_DIRECTORY"],
        system_root=os.environ["SYSTEM_ROOT_DIRECTORY"],
    )


def configure_cognee(settings: Settings) -> None:
    """Push settings into Cognee explicitly.

    We set both the LLM and embedding providers so Cognee never silently
    falls back to OpenAI for embeddings (the classic gotcha).
    """
    import cognee

    llm_cfg = {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "llm_api_key": settings.llm_api_key,
    }
    if settings.llm_endpoint:
        llm_cfg["llm_endpoint"] = settings.llm_endpoint
    cognee.config.set_llm_config(llm_cfg)
    cognee.config.set_embedding_config(
        {
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
        }
    )
