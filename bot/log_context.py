"""Correlation id for the log lines produced while one Telegram update is handled.

python-telegram-bot hands each update to its own asyncio task, and a task copies
the context that was current when it was created. A ContextVar set by the update
middleware is therefore visible to every coroutine handling that update, and it
never leaks into the task handling a concurrent one.
"""

import contextvars
import logging

NO_UPDATE = "-"

current_update_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_update_id", default=NO_UPDATE)


def update_marker(update_id: object) -> str:
    """The tag shared by every line logged while an update is handled."""
    return f"u{update_id}" if isinstance(update_id, int) else NO_UPDATE


def begin_update(update: object) -> str:
    """Tag the current context and return the tag."""
    marker = update_marker(getattr(update, "update_id", None))
    current_update_id.set(marker)
    return marker


class CorrelationFilter(logging.Filter):
    """Stamp every record with the update being handled, so lines can be grouped.

    A filter rather than a ``LogRecord`` factory: the field then exists exactly on
    the handlers we attach it to, and a record built by a library logger that
    never passes through this filter cannot break ``%(correlation_id)s``.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = current_update_id.get()
        return True
