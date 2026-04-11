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

from pipeline.validator import build_empty_result

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


def unwrap_raw_response(result: dict[str, Any]) -> dict[str, Any]:
    """
    If the model returned {"raw_response": "..."} without full_report, try to parse inner JSON.
    """
    if "raw_response" not in result or "full_report" in result:
        return result
    try:
        raw = result["raw_response"]
        if not isinstance(raw, str):
            return result
        raw = re.sub(r"^```json\s*", "", raw.strip())
        raw = re.sub(r"\s*```\s*$", "", raw).strip()
        inner = json.loads(raw)
        if isinstance(inner, dict):
            return inner
    except Exception:
        pass
    return result


def add_character_count(result: dict[str, Any]) -> dict[str, Any]:
    """Total character count in brief_report_json (Beles-style payloads)."""
    br = result.get("brief_report_json")
    if not isinstance(br, dict):
        return result
    total = 0
    for s in br.get("sections") or []:
        if isinstance(s, dict):
            rec = s.get("recommendation", "")
            if isinstance(rec, str):
                total += len(rec)
    overall = br.get("overall_recommendation", "")
    if isinstance(overall, str):
        total += len(overall)
    br["character_count"] = total
    return result


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


async def evaluate_with_llm(
    rubric: str,
    student_work: str,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    user_content: str | None = None,
) -> tuple[str, dict[str, int]]:
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
    if user_content is None:
        user_content = get_evaluation_prompt(rubric, student_work)

    use_model = model or settings.NITEC_MODEL
    use_temp = 0.1 if temperature is None else float(temperature)
    use_max = int(max_tokens if max_tokens is not None else settings.NITEC_MAX_TOKENS)

    async with sem:
        response = await client.chat.completions.create(
            model=use_model,
            temperature=use_temp,
            max_tokens=use_max,
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
