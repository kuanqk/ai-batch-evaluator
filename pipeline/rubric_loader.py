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


def resolve_rubric_for_pipeline(text: str, config) -> tuple[str, str]:
    """
    Return (rubric_markdown, lang) using EvaluatorConfig.rubric when set,
    else filesystem rubrics via get_rubric().
    `config` is EvaluatorConfig | None.
    """
    if not config or not getattr(config, "rubric_id", None):
        return get_rubric(text)

    rub = config.rubric
    mode = config.language_mode

    def _body_for_lang(lang_code: str) -> str:
        return rub.get_text(lang_code)

    if mode == "ru":
        body = _body_for_lang("ru") or _body_for_lang("kk")
        if body.strip():
            return body, "ru"
        return get_rubric(text)
    if mode == "kk":
        body = _body_for_lang("kk") or _body_for_lang("ru")
        if body.strip():
            return body, "kk"
        return get_rubric(text)

    sample = (text or "")[:500]
    if not sample.strip():
        body = _body_for_lang("ru") or _body_for_lang("kk")
        return (body or get_rubric(text)[0], "ru")

    try:
        code = detect(sample)
    except Exception:
        code = "ru"
    lang = "kk" if code in ("kk", "kz") else "ru"
    body = _body_for_lang(lang) or _body_for_lang("kk" if lang == "ru" else "ru")
    if body.strip():
        return body, lang
    return get_rubric(text)
