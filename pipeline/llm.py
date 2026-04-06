"""NITEC LLM client, JSON parsing, score extraction."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from openai import AsyncOpenAI

from django.conf import settings

from config.concurrency import llm_semaphore
from prompt_template import get_evaluation_prompt

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "Отвечай ТОЛЬКО валидным JSON без markdown."


def parse_llm_response(raw: str | None) -> Optional[dict[str, Any]]:
    """Strip thinking blocks / markdown fences; parse JSON."""
    if raw is None or not str(raw).strip():
        return None
    text = str(raw).strip()

    text = re.sub(
        r"<think>.*?</redacted_thinking>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if m:
        inner = m.group(1).strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            pass

    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _level_from_points(total: int, max_points: int = 75) -> int:
    if max_points <= 0:
        return 1
    pct = (total / max_points) * 100.0
    if pct <= 25:
        return 1
    if pct <= 50:
        return 2
    if pct <= 75:
        return 3
    return 4


def extract_scores(result: dict[str, Any]) -> tuple[dict[str, int], float, int]:
    """Returns (scores_dict s1_c1..s5_c5, total_score, level)."""
    scores: dict[str, int] = {f"s{s}_c{c}": 0 for s in range(1, 6) for c in range(1, 6)}
    total = 0.0

    fr = result.get("full_report") or {}
    sections = fr.get("sections") or []
    for sec in sections:
        try:
            sn = int(sec.get("section_number") or 0)
        except (TypeError, ValueError):
            continue
        for crit in sec.get("criteria") or []:
            try:
                cn = int(crit.get("criterion_number") or 0)
            except (TypeError, ValueError):
                continue
            try:
                sc = int(crit.get("score") or 0)
            except (TypeError, ValueError):
                sc = 0
            key = f"s{sn}_c{cn}"
            if key in scores:
                scores[key] = sc
                total += sc

    level = _level_from_points(int(total))
    overall = fr.get("overall_score") or {}
    if isinstance(overall, dict) and overall.get("level") is not None:
        try:
            level = int(overall["level"])
        except (TypeError, ValueError):
            pass

    return scores, total, level


def build_empty_result(reason: str) -> dict[str, Any]:
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


async def evaluate_with_llm(rubric: str, student_work: str) -> tuple[str, dict[str, int]]:
    """Returns (raw_response, usage dict with token counts)."""
    if not settings.NITEC_API_KEY:
        raise ValueError("NITEC_API_KEY is not set")

    sem = llm_semaphore
    if sem is None:
        raise RuntimeError("llm_semaphore not initialized; call init_concurrency() first")

    client = AsyncOpenAI(
        base_url=settings.NITEC_BASE_URL.rstrip("/"),
        api_key=settings.NITEC_API_KEY,
    )
    user_content = get_evaluation_prompt(rubric, student_work)

    async with sem:
        response = await client.chat.completions.create(
            model=settings.NITEC_MODEL,
            temperature=0.1,
            max_tokens=settings.NITEC_MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )

    choice = response.choices[0].message
    raw = choice.content
    if raw is None:
        logger.warning("LLM returned empty content (reasoning in progress?)")
        raw = ""

    usage_obj = response.usage
    usage = {
        "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0) if usage_obj else 0,
        "completion_tokens": getattr(usage_obj, "completion_tokens", 0) if usage_obj else 0,
    }
    return raw, usage
