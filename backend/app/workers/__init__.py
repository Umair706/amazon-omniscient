"""Celery workers package — exposes the celery_app instance for CLI discovery."""

from app.workers.celery_app import celery_app

__all__ = ["celery_app"]
