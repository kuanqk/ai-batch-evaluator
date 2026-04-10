"""File validation, docx repair, and empty-result helpers."""

from __future__ import annotations

import io
import logging
import zipfile
from typing import Any

logger = logging.getLogger(__name__)


def check_truncated_zip(file_content: bytes, filename: str) -> bool:
    """
    Returns True if the file looks like a ZIP-based docx but is corrupted/truncated.
    """
    if not filename.lower().endswith(".docx"):
        return False
    if len(file_content) < 2 or file_content[:2] != b"PK":
        return False
    try:
        zipfile.ZipFile(io.BytesIO(file_content)).namelist()
    except zipfile.BadZipFile:
        return True
    return False


def fix_broken_docx(path: str) -> bool:
    """
    Removes NULL image references in .rels files inside a docx zip (in-place).
    Returns True if any file was modified.
    """
    try:
        with zipfile.ZipFile(path, "r") as zin:
            names = zin.namelist()
            rel_updates: dict[str, bytes] = {}
            for name in names:
                if not name.endswith(".rels"):
                    continue
                data = zin.read(name)
                if b"NULL" not in data:
                    continue
                new_data = data.replace(b'Target="../NULL"', b'Target=""')
                new_data = new_data.replace(b"../NULL", b"")
                if new_data != data:
                    rel_updates[name] = new_data
            if not rel_updates:
                return False
            out_buf = io.BytesIO()
            with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
                for name in names:
                    if name in rel_updates:
                        zout.writestr(name, rel_updates[name])
                    else:
                        zout.writestr(name, zin.read(name))
        with open(path, "wb") as f:
            f.write(out_buf.getvalue())
        return True
    except (zipfile.BadZipFile, OSError) as e:
        logger.warning("fix_broken_docx failed for %s: %s", path, e)
        return False


def build_empty_result(reason: str) -> dict[str, Any]:
    """Structured JSON with zero scores — for invalid/empty documents (status=done path in pipeline)."""
    return {
        "validation": {
            "is_valid": False,
            "is_substantive": False,
            "is_on_topic": False,
            "failure_reason": reason,
        },
        "teacher_name": "Не указано",
        "topic": "Не указано",
        "full_report": {
            "overall_score": {
                "total_points": 0,
                "max_points": 75,
                "percentage": 0.0,
                "level": 1,
            },
            "sections": [],
            "top_strengths": [],
            "critical_gaps": [],
        },
        "brief_report_json": {
            "sections": [],
            "overall_recommendation": reason,
        },
        "level_assessment": {
            "level": 1,
            "description": "Документ не подлежит полноценной оценке",
            "justification": reason,
        },
    }


def is_text_sufficient(text: str, min_chars: int = 50) -> bool:
    """Whether extracted text is long enough for rubric + LLM."""
    return len((text or "").strip()) >= min_chars
