from __future__ import annotations

import re
from pathlib import Path

from pyclaw.config.schema import PyClawConfig

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = PROJECT_ROOT / "docs" / "configuration.md"

_ALLOWED_DOC_ONLY_KEYS = {"backup"}


def _extract_doc_top_level_keys(text: str) -> set[str]:
    section_start = text.find("## 顶层配置节一览")
    if section_start >= 0:
        tail = text[section_start:]
        section_end = tail.find("\n---")
        if section_end > 0:
            text = tail[:section_end]
        else:
            text = tail
    keys = set()
    for line in text.splitlines():
        match = re.match(r"^\|\s*`([a-zA-Z0-9_]+)`\s*\|", line)
        if match:
            keys.add(match.group(1))
    return keys


def test_configuration_doc_top_level_keys_are_known() -> None:
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    doc_keys = _extract_doc_top_level_keys(doc_text)

    schema_keys = set(PyClawConfig.model_fields.keys())
    unknown = sorted(k for k in doc_keys if k not in schema_keys and k not in _ALLOWED_DOC_ONLY_KEYS)
    assert not unknown, f"Unknown documented top-level config keys: {unknown}"


def test_skills_section_documents_discovery_order() -> None:
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    assert "Skills 来源与发现顺序" in doc_text
    assert "PYCLAW_BUNDLED_SKILLS" in doc_text
