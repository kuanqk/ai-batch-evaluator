"""Download remote files (OneDrive, Google Docs, direct URL)."""

from __future__ import annotations

import logging
import re
from email.message import EmailMessage
from urllib.parse import parse_qs, urlparse, urlunparse

import httpx

from config.concurrency import download_semaphore

logger = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT = 60.0


def _normalize_url(url: str) -> str:
    u = url.strip()
    parsed = urlparse(u)
    host = (parsed.netloc or "").lower()
    path = parsed.path or ""

    if "1drv.ms" in host or "onedrive.live.com" in host or "sharepoint.com" in host:
        q = parse_qs(parsed.query)
        if "download" not in q:
            sep = "&" if parsed.query else ""
            new_query = f"{parsed.query}{sep}download=1" if parsed.query else "download=1"
            return urlunparse(
                (
                    parsed.scheme or "https",
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment,
                )
            )

    m = re.search(r"/document/d/([a-zA-Z0-9_-]+)", path)
    if m and ("docs.google.com" in host):
        doc_id = m.group(1)
        export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=pdf"
        return export_url

    return u


def _filename_from_disposition(header: str | None) -> str | None:
    if not header:
        return None
    msg = EmailMessage()
    msg["Content-Disposition"] = header
    return msg.get_filename()


def _filename_from_url(url: str) -> str:
    path = urlparse(url).path
    base = path.rstrip("/").split("/")[-1]
    if base and "." in base:
        return base
    return "document.pdf"


async def download_file(url: str) -> tuple[bytes, str]:
    """Returns (content_bytes, filename)."""
    final_url = _normalize_url(url)
    sem = download_semaphore
    if sem is None:
        raise RuntimeError("download_semaphore not initialized; call init_concurrency() first")

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; OrleuBatchEvaluator/1.0)",
    }
    async with sem:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=DOWNLOAD_TIMEOUT,
            headers=headers,
        ) as client:
            resp = await client.get(final_url)
            resp.raise_for_status()
            data = resp.content
            cd = resp.headers.get("content-disposition")
            resolved = str(resp.url)

    if len(data) < 1000:
        logger.warning("Downloaded file is very small (%s bytes); may be corrupt", len(data))

    name = _filename_from_disposition(cd) or _filename_from_url(resolved)
    return data, name
