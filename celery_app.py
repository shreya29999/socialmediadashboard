from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv
import os

load_dotenv()

# SECTION 1 — CELERY APP INIT

celery_app = Celery(
    "social_dashboard",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=["tasks"]
)

# SECTION 2 — CELERY CONFIGURATION

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

# SECTION 3 — BEAT SCHEDULE (What Runs automaticallyand what runs when )

celery_app.conf.beat_schedule = {
    "send-confirmations-every-minute": {
        "task"    : "tasks.send_confirmation_task",
        "schedule": 60.0, 
    },
    "check-expired-every-minute": {
        "task"    : "tasks.expiry_checker_task",
        "schedule": 60.0, 
    },
    "daily-ai-post-generation": {
        "task"    : "tasks.generate_ai_posts_task",
        "schedule": crontab(hour=8, minute=0)
    },

}