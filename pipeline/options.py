"""Resolved pipeline options from Django settings or EvaluatorConfig."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from apps.evaluators.models import EvaluatorConfig


@dataclass(frozen=True)
class PipelineOptions:
    min_text_chars: int
    vision_max_pages: int
    vision_dpi: int
    vision_model: str
    llm_model: str
    temperature: float
    max_tokens: int
    enable_doc_fix: bool
    enable_google_docs: bool
    enable_python_docx: bool
    enable_pymupdf_fallback: bool
    enable_vision_ocr: bool

    def min_pdf_chars(self) -> int:
        return max(self.min_text_chars, 100)

    def vision_model_effective(self) -> str | None:
        if not self.enable_vision_ocr or self.vision_model in ("none", ""):
            return None
        return self.vision_model


def build_pipeline_options(config: EvaluatorConfig | None) -> PipelineOptions:
    if config is None:
        return PipelineOptions(
            min_text_chars=int(getattr(settings, "MIN_TEXT_CHARS", 50)),
            vision_max_pages=int(getattr(settings, "VISION_MAX_PAGES", 10)),
            vision_dpi=int(getattr(settings, "VISION_DPI", 150)),
            vision_model=str(getattr(settings, "NITEC_VISION_MODEL", "")),
            llm_model=str(getattr(settings, "NITEC_MODEL", "")),
            temperature=0.1,
            max_tokens=int(getattr(settings, "NITEC_MAX_TOKENS", 4096)),
            enable_doc_fix=True,
            enable_google_docs=True,
            enable_python_docx=True,
            enable_pymupdf_fallback=True,
            enable_vision_ocr=True,
        )
    return PipelineOptions(
        min_text_chars=int(config.min_text_chars),
        vision_max_pages=int(config.vision_max_pages),
        vision_dpi=int(config.vision_dpi),
        vision_model=str(config.vision_model or ""),
        llm_model=str(config.llm_model),
        temperature=float(config.temperature),
        max_tokens=int(config.max_tokens),
        enable_doc_fix=bool(config.enable_doc_fix),
        enable_google_docs=bool(config.enable_google_docs),
        enable_python_docx=bool(config.enable_python_docx),
        enable_pymupdf_fallback=bool(config.enable_pymupdf_fallback),
        enable_vision_ocr=bool(config.enable_vision_ocr),
    )
