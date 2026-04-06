"""Async semaphores for external services.

Initialized lazily — called at the start of each asyncio.run() in Celery tasks
so semaphores belong to the correct event loop.
"""

import asyncio

from django.conf import settings

download_semaphore: asyncio.Semaphore | None = None
llm_semaphore: asyncio.Semaphore | None = None
vision_semaphore: asyncio.Semaphore | None = None


def init_concurrency() -> None:
    global download_semaphore, llm_semaphore, vision_semaphore
    download_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_DOWNLOADS)
    llm_semaphore = asyncio.Semaphore(settings.NITEC_MAX_WORKERS)
    vision_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_VISION)
