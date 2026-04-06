"""Extract text from docx/pdf; Vision OCR fallback."""

from __future__ import annotations

import base64
import logging
import re
from pathlib import Path

import fitz
from openai import AsyncOpenAI

from django.conf import settings

from config.concurrency import vision_semaphore

from pipeline.converter import convert_docx_to_pdf
from pipeline.docx_utils import extract_text_from_docx_xml

logger = logging.getLogger(__name__)

MIN_TEXT_CHARS_DOCX = 50
MIN_TEXT_CHARS_PDF = 100
VISION_MAX_PAGES = 10
VISION_DPI = 150


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    text_parts: list[str] = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        logger.warning("PyMuPDF open failed: %s", e)
        return ""
    try:
        for i in range(len(doc)):
            page = doc.load_page(i)
            text_parts.append(page.get_text() or "")
    finally:
        doc.close()
    text = "\n".join(text_parts)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


async def vision_ocr(pdf_bytes: bytes, max_pages: int = VISION_MAX_PAGES) -> str:
    """Render PDF pages to PNG (base64) and call vision model."""
    sem = vision_semaphore
    if sem is None:
        raise RuntimeError("vision_semaphore not initialized; call init_concurrency() first")
    if not settings.NITEC_API_KEY:
        raise ValueError("NITEC_API_KEY is not set for Vision OCR")

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        logger.warning("vision_ocr: cannot open PDF: %s", e)
        return ""

    images_b64: list[str] = []
    try:
        n = min(len(doc), max_pages)
        matrix = fitz.Matrix(VISION_DPI / 72.0, VISION_DPI / 72.0)
        for i in range(n):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            png = pix.tobytes("png")
            images_b64.append(base64.b64encode(png).decode("ascii"))
    finally:
        doc.close()

    if not images_b64:
        return ""

    client = AsyncOpenAI(
        base_url=settings.NITEC_BASE_URL.rstrip("/"),
        api_key=settings.NITEC_API_KEY,
    )

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "Извлеки весь читаемый текст с этих страниц документа. "
                "Сохрани порядок и структуру абзацев. Без комментариев, только текст."
            ),
        }
    ]
    for b64 in images_b64:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            }
        )

    async with sem:
        response = await client.chat.completions.create(
            model=settings.NITEC_VISION_MODEL,
            temperature=0.0,
            max_tokens=8192,
            messages=[{"role": "user", "content": content}],
        )

    raw = response.choices[0].message.content
    return (raw or "").strip()


async def extract_text(content: bytes, filename: str) -> tuple[str, str]:
    """
    Returns (text, method) where method is xml|pdf_text|vision_ocr|plain|empty.
    """
    ext = Path(filename).suffix.lower()

    if ext == ".txt":
        try:
            t = content.decode("utf-8")
        except UnicodeDecodeError:
            t = content.decode("utf-8", errors="replace")
        t = t.strip()
        return t, "plain"

    if ext == ".pdf":
        text = extract_text_from_pdf(content)
        if len(text) >= MIN_TEXT_CHARS_PDF:
            return text, "pdf_text"
        if len(text) < MIN_TEXT_CHARS_PDF:
            ocr = await vision_ocr(content)
            if len(ocr.strip()) >= MIN_TEXT_CHARS_PDF:
                return ocr.strip(), "vision_ocr"
        return text, "pdf_text" if text else "empty"

    if ext == ".docx":
        text = extract_text_from_docx_xml(content)
        if len(text) >= MIN_TEXT_CHARS_DOCX:
            return text, "xml"
        pdf_bytes = await convert_docx_to_pdf(content)
        if pdf_bytes:
            text = extract_text_from_pdf(pdf_bytes)
            if len(text) >= MIN_TEXT_CHARS_DOCX:
                return text, "pdf_text"
            if len(text) < MIN_TEXT_CHARS_DOCX:
                ocr = await vision_ocr(pdf_bytes)
                if len(ocr.strip()) >= MIN_TEXT_CHARS_DOCX:
                    return ocr.strip(), "vision_ocr"
        return text, "xml" if text else "empty"

    # Fallback: try as docx zip
    text = extract_text_from_docx_xml(content)
    if text and len(text) >= MIN_TEXT_CHARS_DOCX:
        return text, "xml"
    return text, "empty"
