"""Best-effort step tracking using Django ORM (sync, fire-and-forget)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def track_step(eval_id: int, step: int, status: str) -> None:
    """Update current_step on an Evaluation; swallows all errors."""
    try:
        from apps.batch.models import Evaluation
        Evaluation.objects.filter(pk=eval_id).update(current_step=step)
    except Exception:
        logger.exception("[eval=%s] tracker step=%s status=%s failed", eval_id, step, status)
