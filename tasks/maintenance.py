"""Maintenance tasks: cleanup, housekeeping."""

from __future__ import annotations

import logging
import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from config.celery import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.maintenance.cleanup_tmp")
def cleanup_tmp() -> None:
    """Remove temp files older than 1 hour."""
    tmp = Path(settings.TMP_DIR)
    if not tmp.exists():
        return
    cutoff = timezone.now() - timedelta(hours=1)
    removed = 0
    for f in tmp.rglob("*"):
        if f.is_file():
            mtime = timezone.datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                try:
                    f.unlink()
                    removed += 1
                except OSError:
                    pass
    logger.info("cleanup_tmp: removed %s files", removed)


@celery_app.task(name="tasks.maintenance.ping")
def ping() -> str:
    return "ok"
