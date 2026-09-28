from celery import Celery
from celery.schedules import crontab
from app.core.config import REDIS_URL

# CELERY APP INIT

celery_app = Celery(
    "social_dashboard",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.workers.tasks"],
)

# CELERY CONFIGURATION

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=86400,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)

# CELERY BEAT SCHEDULE

celery_app.conf.beat_schedule = {
    "send-confirmations-every-minute": {
        "task": "tasks.send_confirmation_task",
        "schedule": 60.0,
    },

    "check-expired-every-minute": {
        "task": "tasks.expiry_checker_task",
        "schedule": 60.0,
    },

    "publish-due-posts-every-minute": {
        "task": "tasks.publish_due_posts_task",
        "schedule": 60.0,
    },

    "daily-ai-post-generation": {
        "task": "tasks.generate_ai_posts_for_all_users",
        "schedule": crontab(hour=8, minute=0),
        "options": {"expires": 3600},
    },
}