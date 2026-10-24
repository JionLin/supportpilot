"""Document loaders for PDF, Markdown, TXT, and URL sources.

@author jiaolin
"""

from __future__ import annotations

from pathlib import Path

import httpx
import trafilatura
from pypdf import PdfReader


async def load_text_from_path(path: Path, source_type: str) -> str:
    """Load plain text from a local file.

    Args:
        path: Filesystem path.
        source_type: One of pdf/md/txt.

    Returns:
        str: Extracted text.

    Raises:
        ValueError: When source_type is unsupported or file is empty.
    """
    if source_type == "pdf":
        reader = PdfReader(str(path))
        parts = [(page.extract_text() or "") for page in reader.pages]
        text = "\n\n".join(parts).strip()
    elif source_type in {"md", "txt"}:
        text = path.read_text(encoding="utf-8").strip()
    else:
        msg = f"Unsupported source_type for path load: {source_type}"
        raise ValueError(msg)
    if not text:
        msg = f"No text extracted from {path}"
        raise ValueError(msg)
    return text


async def load_text_from_url(url: str, *, timeout_s: float = 15.0) -> str:
    """Fetch a URL and extract main article text with trafilatura.

    Args:
        url: HTTP(S) URL.
        timeout_s: Request timeout.

    Returns:
        str: Extracted main text.

    Raises:
        ValueError: When extraction fails.
    """
    async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text
    extracted = trafilatura.extract(html, include_comments=False, include_tables=True)
    if not extracted or not extracted.strip():
        msg = f"No text extracted from URL: {url}"
        raise ValueError(msg)
    return extracted.strip()
