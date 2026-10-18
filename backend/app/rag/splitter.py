"""Heading-aware text splitter with fixed size and overlap.

@author jiaolin
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"(?m)^(#{1,6}\s+.+)$")

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 120


@dataclass(frozen=True)
class TextChunk:
    """A single text chunk with ordinal index."""

    index: int
    content: str
    heading: str | None = None


def split_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[TextChunk]:
    """Split text by markdown headings then by length with overlap.

    Args:
        text: Source document text.
        chunk_size: Max characters per chunk.
        chunk_overlap: Overlap characters between adjacent chunks.

    Returns:
        list[TextChunk]: Ordered chunks.
    """
    if chunk_size <= 0:
        msg = "chunk_size must be positive"
        raise ValueError(msg)
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        msg = "chunk_overlap must be >= 0 and < chunk_size"
        raise ValueError(msg)

    sections = _split_by_headings(text)
    chunks: list[TextChunk] = []
    for heading, body in sections:
        for piece in _window(body, chunk_size, chunk_overlap):
            content = piece if heading is None else f"{heading}\n\n{piece}"
            content = content.strip()
            if not content:
                continue
            chunks.append(
                TextChunk(index=len(chunks), content=content, heading=heading)
            )
    if not chunks and text.strip():
        chunks.append(TextChunk(index=0, content=text.strip(), heading=None))
    return chunks


def _split_by_headings(text: str) -> list[tuple[str | None, str]]:
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return [(None, text)]

    sections: list[tuple[str | None, str]] = []
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append((None, preamble))

    for index, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append((heading, body or heading))
    return sections


def _window(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text else []
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        parts.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - chunk_overlap)
    return parts
