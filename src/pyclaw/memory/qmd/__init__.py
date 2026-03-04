"""QMD integration — external memory backend for Q&A/knowledge retrieval.

QMD (Query Memory Database) provides a structured store for long-term
knowledge that can be queried semantically via the memory subsystem.
"""

from pyclaw.memory.qmd.store import QmdEntry, QmdStore

__all__ = ["QmdEntry", "QmdStore"]
