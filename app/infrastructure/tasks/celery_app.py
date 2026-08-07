from __future__ import annotations

from celery import Celery

from app.config.settings import get_settings

settings = get_settings()


def make_celery() -> Celery:
    broker = f"redis://{settings.redis_host}:{settings.redis_port}/0"
    backend = f"redis://{settings.redis_host}:{settings.redis_port}/1"
    app = Celery("phoenixrag.tasks", broker=broker, backend=backend)
    # minimal config; real deployments configure task routes, serializers, and retries
    app.conf.task_acks_late = True
    app.conf.worker_prefetch_multiplier = 1
    return app


celery_app = make_celery()
