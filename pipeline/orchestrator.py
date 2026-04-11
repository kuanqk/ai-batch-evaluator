"""End-to-end pipeline: URL → text → rubric → LLM → structured result."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from pipeline.converter import convert_to_docx
from pipeline.downloader import download_file
from pipeline.extractor import extract_text
from pipeline.llm import (
    add_character_count,
    evaluate_with_llm,
    extract_scores,
    parse_llm_response,
    unwrap_raw_response,
)
from pipeline.options import build_pipeline_options
from pipeline.parser import parse_file_path
from pipeline.rubric_loader import resolve_rubric_for_pipeline
from pipeline.validator import (
    build_empty_result,
    check_truncated_zip,
    fix_broken_docx,
    is_text_sufficient,
)

logger = logging.getLogger(__name__)

SUPPORTED_EXT = {".doc", ".docx", ".pdf", ".odt", ".rtf", ".txt"}


async def run_pipeline(
    url: str,
    file_path: str | None = None,
    *,
    extract_only: bool = False,
    eval_config: Any | None = None,
) -> dict[str, Any]:
    """
    Download URL, extract text, optionally run LLM evaluation.
    If file_path is None, uses a placeholder path for parser metadata.
    When extract_only is True, skips LLM (returns extraction + rubric only).
    eval_config: optional EvaluatorConfig instance (DB-loaded in the caller).
    """
    opts = build_pipeline_options(eval_config)

    meta: dict[str, Any] = {}
    if file_path:
        parsed = parse_file_path(file_path)
        meta = {
            "program": parsed.program,
            "city": parsed.city,
            "trainer": parsed.trainer,
            "group_name": parsed.group_name,
            "file_name": parsed.file_name,
        }
    else:
        meta = {
            "program": "",
            "city": "",
            "trainer": "",
            "group_name": "",
            "file_name": "",
        }

    content, dl_name = await download_file(url, enable_google_docs=opts.enable_google_docs)
    file_size_bytes = len(content)
    filename = meta.get("file_name") or dl_name
    if not Path(filename).suffix and Path(dl_name).suffix:
        filename = dl_name

    ext = Path(filename).suffix.lower()
    if ext and ext not in SUPPORTED_EXT:
        result = build_empty_result("Файл не является поддерживаемым документом (ожидаются doc/docx/pdf/odt/rtf)")
        result["meta"] = meta
        result["download_filename"] = dl_name
        result["file_size_bytes"] = file_size_bytes
        result["doc_chars"] = 0
        result["used_fix_docx"] = False
        result["used_vision_ocr"] = False
        return result

    content, filename = await convert_to_docx(content, filename)
    ext = Path(filename).suffix.lower()

    if ext == ".docx" and check_truncated_zip(content, filename):
        result = build_empty_result("Файл повреждён или обрезан")
        result["meta"] = meta
        result["download_filename"] = dl_name
        result["file_size_bytes"] = file_size_bytes
        result["doc_chars"] = 0
        result["used_fix_docx"] = False
        result["used_vision_ocr"] = False
        result["was_empty_doc"] = True
        return result

    used_fix_docx = False
    if ext == ".docx" and opts.enable_doc_fix:
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tf:
            tf.write(content)
            tmp_path = tf.name
        try:
            if fix_broken_docx(tmp_path):
                used_fix_docx = True
                content = Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    text, method = await extract_text(content, filename, opts)
    doc_chars = len(text)
    min_chars = opts.min_text_chars
    if not is_text_sufficient(text, min_chars):
        result = build_empty_result("Документ пуст или не содержит текста")
        result["meta"] = meta
        result["extraction_method"] = method
        result["download_filename"] = dl_name
        result["file_size_bytes"] = file_size_bytes
        result["doc_chars"] = doc_chars
        result["used_fix_docx"] = used_fix_docx
        result["used_vision_ocr"] = method == "vision_ocr"
        result["was_empty_doc"] = True
        return result

    rubric, lang = resolve_rubric_for_pipeline(text, eval_config)

    out: dict[str, Any] = {
        "meta": meta,
        "download_filename": dl_name,
        "normalized_filename": filename,
        "extraction_method": method,
        "doc_lang": lang,
        "text_preview": text[:2000],
        "file_size_bytes": file_size_bytes,
        "doc_chars": doc_chars,
        "used_fix_docx": used_fix_docx,
        "used_vision_ocr": method == "vision_ocr",
        "was_empty_doc": False,
    }

    if extract_only:
        out["rubric_preview"] = rubric[:1500]
        return out

    user_content = None
    if eval_config is not None and getattr(eval_config, "prompt_template_id", None):
        user_content = eval_config.prompt_template.render(rubric, text)

    raw, usage = await evaluate_with_llm(
        rubric,
        text,
        model=opts.llm_model,
        temperature=opts.temperature,
        max_tokens=opts.max_tokens,
        user_content=user_content,
    )
    parsed = parse_llm_response(raw)
    if not parsed:
        logger.error("LLM response could not be parsed as JSON")
        result = build_empty_result("Не удалось разобрать ответ модели как JSON")
        result.update(out)
        result["llm_raw"] = raw[:5000]
        result["usage"] = usage
        return result

    parsed = unwrap_raw_response(parsed)
    parsed = add_character_count(parsed)

    scores, total, level = extract_scores(parsed)
    out["llm_result"] = parsed
    out["scores"] = scores
    out["total_score"] = total
    out["score_level"] = level
    out["usage"] = usage
    out["llm_raw"] = raw
    return out
