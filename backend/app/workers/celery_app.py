"""Celery application instance and configuration."""

from celery import Celery
from celery.schedules import crontab

from app.config import Settings

settings = Settings()

celery_app = Celery(
    "omniscient",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task behaviour
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Result expiry (24 hours)
    result_expires=86400,
    # Task routing
    task_routes={
        "app.workers.tasks.run_full_analysis": {"queue": "analysis"},
        "app.workers.tasks.track_bsr_prices": {"queue": "tracking"},
        "app.workers.tasks.scrape_reviews": {"queue": "scraping"},
        "app.workers.tasks.refresh_competitor_data": {"queue": "analysis"},
        "app.workers.tasks.compute_velocity_snapshots": {"queue": "analysis"},
    },
    # Default queue for unrouted tasks
    task_default_queue="default",
    # Beat schedule — periodic tasks
    beat_schedule={
        "track-bsr-prices-every-6h": {
            "task": "app.workers.tasks.track_bsr_prices_all",
            "schedule": crontab(minute=0, hour="*/6"),
            "options": {"queue": "tracking"},
        },
        "refresh-competitors-daily": {
            "task": "app.workers.tasks.refresh_all_competitors",
            "schedule": crontab(minute=30, hour=2),  # 2:30 AM UTC
            "options": {"queue": "analysis"},
        },
        "cleanup-old-projections-weekly": {
            "task": "app.workers.tasks.cleanup_old_data",
            "schedule": crontab(minute=0, hour=3, day_of_week=0),  # Sunday 3 AM
            "options": {"queue": "default"},
        },
        "compute-velocity-daily": {
            "task": "app.workers.tasks.compute_velocity_snapshots",
            "schedule": crontab(minute=30, hour=1),  # 1:30 AM UTC daily
            "options": {"queue": "analysis"},
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.workers"])
