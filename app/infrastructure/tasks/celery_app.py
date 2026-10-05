from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.config.settings import get_settings


try:
    from celery import Celery
except ImportError:  # pragma: no cover - used only when dependencies are not installed
    class _LocalTask:
        def __init__(self, function: Callable[..., Any], bind: bool) -> None:
            self._function = function
            self._bind = bind

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            return self._function(self, *args, **kwargs) if self._bind else self._function(*args, **kwargs)

        def delay(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("Celery is not installed; background tasks cannot be queued")

        def apply_async(
            self,
            args: tuple[Any, ...] | list[Any] | None = None,
            kwargs: dict[str, Any] | None = None,
            **options: Any,
        ) -> Any:
            raise RuntimeError("Celery is not installed; background tasks cannot be queued")

        def retry(self, exc: Exception | None = None, **_: Any) -> None:
            if exc:
                raise exc
            raise RuntimeError("local task retry requested")

    class _LocalCelery:
        def task(self, *_, bind: bool = False, **__: Any) -> Callable[[Callable[..., Any]], _LocalTask]:
            def decorate(function: Callable[..., Any]) -> _LocalTask:
                return _LocalTask(function, bind)

            return decorate

    celery_app = _LocalCelery()
else:
    settings = get_settings()
    celery_app = Celery(
        "phoenixrag",
        broker=settings.effective_celery_broker_url,
        backend=settings.effective_celery_result_backend,
        include=[
            "app.application.tasks.embed_document",
            "app.application.tasks.index_document",
            "app.application.tasks.chunk_document",
        ],
    )
    celery_app.conf.update(task_track_started=True, task_serializer="json", accept_content=["json"])