"""Teach-file parsing: markdown/notes -> sprite knowledge entries. No network.

``awsprite teach`` feeds the companion from a file. Two layouts are
understood, both deterministic:

* Markdown sections: any ``#`` heading opens a section — the heading text
  is the entry TITLE and the lines until the next heading are the CONTENT.
* Plain notes (no headings): the file is split on blank lines; the first
  non-blank line of each chunk is the TITLE, the rest is the CONTENT.

Titles and content are truncated to the service's own limits (120/4000 —
the engine's MAX_KNOWLEDGE_TITLE / MAX_KNOWLEDGE_CONTENT), never sent whole.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from awsprite.model import KNOWLEDGE_KINDS, MAX_CONTENT, MAX_TITLE, SpriteError


def parse_teach_entries(text: str, default_kind: str = "fact") -> List[Dict[str, Any]]:
    """Split a markdown/notes file into teach entries.

    Args:
        text: the file's contents (CRLF or LF).
        default_kind: knowledge kind applied to every entry produced.

    Returns:
        A list of ``{"kind", "title", "content"}`` dicts ready to feed to
        ``SpriteClient.teach``. An empty or blank file yields no entries.

    Raises:
        SpriteError: ``default_kind`` is not a knowledge kind the teach
            surface accepts.
    """
    if default_kind not in KNOWLEDGE_KINDS:
        raise SpriteError(
            f"unknown knowledge kind: {default_kind!r} "
            f"(choose from {', '.join(KNOWLEDGE_KINDS)})"
        )
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    entries: List[Dict[str, Any]] = []
    for title, body_lines in _sections(text):
        if title is None:
            # No heading in this chunk: blank-line-separated notes.
            for sub in _blank_line_chunks(body_lines):
                if not sub:
                    continue
                entries.append(_entry(default_kind, sub[0], "\n".join(sub[1:])))
        else:
            entries.append(_entry(default_kind, title, "\n".join(body_lines)))
    return entries


def _sections(text: str) -> List[Tuple[Optional[str], List[str]]]:
    """Chunks delimited by heading lines: (title_or_None, [body lines]).

    Content before the first heading forms a chunk with title None — the
    notes layout. A heading line with no text (``#`` alone) yields a
    heading with title None, which also falls back to the notes layout.
    """
    chunks: List[Tuple[Optional[str], List[str]]] = []
    title: Optional[str] = None
    body: List[str] = []
    for line in text.split("\n"):
        if line.lstrip().startswith("#"):
            chunks.append((title, body))
            title = line.lstrip("#").strip() or None
            body = []
        else:
            body.append(line)
    chunks.append((title, body))
    return chunks


def _blank_line_chunks(lines: List[str]) -> List[List[str]]:
    """Split on blank lines; each chunk is a list of non-blank lines."""
    chunks: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        if line.strip():
            current.append(line)
        elif current:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def _entry(kind: str, title: str, content: str) -> Dict[str, Any]:
    title = title.strip()
    return {
        "kind": kind,
        "title": title[:MAX_TITLE],
        "content": content.strip()[:MAX_CONTENT],
    }
