from .celery import celery_app  # noqa: F401 — ensures Celery is initialized with Django

__all__ = ("celery_app",)
