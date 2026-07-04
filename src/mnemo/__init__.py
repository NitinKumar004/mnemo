"""mnemo — an anti-amnesia coding companion built on Cognee + Claude.

Public surface is intentionally tiny; the CLI (`mnemo.cli`) is the entry point.
The memory layer is abstracted behind `mnemo.memory.base.MemoryBackend` so the
Cognee implementation can be swapped or mocked without touching the CLI.
"""

__version__ = "0.1.0"
