"""Language detection and rubric file selection."""

from __future__ import annotations

import logging
from pathlib import Path

from langdetect import DetectorFactory, detect

from django.conf import settings

logger = logging.getLogger(__name__)

DetectorFactory.seed = 0


def get_rubric(text: str) -> tuple[str, str]:
    """
    Returns (rubric_markdown, lang) where lang is 'ru' or 'kk'.
    """
    sample = (text or "")[:500]
    if not sample.strip():
        return _load_rubric_file("rubric_rus.md"), "ru"

    try:
        code = detect(sample)
    except Exception:
        logger.debug("langdetect failed, defaulting to ru")
        return _load_rubric_file("rubric_rus.md"), "ru"

    # Kazakh ISO 639: kk; langdetect may return other hints for Kazakh text
    if code in ("kk", "kz"):
        return _load_rubric_file("rubric_kaz.md"), "kk"

    return _load_rubric_file("rubric_rus.md"), "ru"


def _load_rubric_file(name: str) -> str:
    base = Path(settings.RUBRICS_DIR)
    path = base / name
    if not path.is_file():
        raise FileNotFoundError(f"Rubric not found: {path}")
    return path.read_text(encoding="utf-8")
