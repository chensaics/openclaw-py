"""Query expansion for FTS-only search mode.

Extracts meaningful keywords from conversational queries
to improve FTS results. Supports multi-language stop words.

Ported from ``src/memory/query-expansion.ts``.
"""

from __future__ import annotations

import re
from typing import Any

STOP_WORDS_EN = frozenset({
    "a", "an", "the", "this", "that", "these", "those",
    "i", "me", "my", "we", "our", "you", "your",
    "he", "she", "it", "they", "them",
    "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "can", "may", "might",
    "in", "on", "at", "to", "for", "of", "with", "by",
    "from", "about", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "over",
    "and", "or", "but", "if", "then", "because", "as",
    "while", "when", "where", "what", "which", "who", "how", "why",
    "yesterday", "today", "tomorrow", "earlier", "later",
    "recently", "ago", "just", "now",
    "thing", "things", "stuff", "something", "anything",
    "everything", "nothing",
    "please", "help", "find", "show", "get", "tell", "give",
})

STOP_WORDS_ZH = frozenset({
    "的", "了", "在", "是", "我", "有", "和", "就",
    "不", "人", "都", "一", "一个", "上", "也", "很",
    "到", "说", "要", "去", "你", "会", "着", "没有",
    "看", "好", "自己", "这", "他", "她", "它",
    "那", "那个", "这个", "什么", "怎么", "哪个",
    "之前", "以前", "最近", "刚才",
})

ALL_STOP_WORDS = STOP_WORDS_EN | STOP_WORDS_ZH

_WORD_RE = re.compile(r"[\w]+", re.UNICODE)


def extract_keywords(query: str) -> list[str]:
    """Extract meaningful keywords from a query, filtering stop words."""
    tokens = _WORD_RE.findall(query.lower())
    keywords = [t for t in tokens if t not in ALL_STOP_WORDS and len(t) > 1]
    return keywords


def expand_query_for_fts(query: str) -> str | None:
    """Build an expanded FTS5 query from a natural-language query.

    Returns a string suitable for SQLite FTS5 MATCH, or None
    if no keywords were extracted.
    """
    keywords = extract_keywords(query)
    if not keywords:
        return None
    # Quote each keyword and join with OR for broader recall
    quoted = [f'"{kw}"' for kw in keywords]
    return " OR ".join(quoted)


def build_fts_query(raw: str) -> str | None:
    """Build a strict FTS5 AND query from raw text tokens."""
    tokens = re.findall(r"[\w]+", raw, re.UNICODE)
    tokens = [t.strip() for t in tokens if t.strip()]
    if not tokens:
        return None
    quoted = [f'"{t}"' for t in tokens]
    return " AND ".join(quoted)
