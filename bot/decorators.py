import functools
from typing import Any, Callable


def rejects_stale_updates(handler: Callable[..., Any]) -> Callable[..., Any]:
    """Drop updates older than the bot's configured message age limit.

    Telegram re-delivers queued updates when the bot restarts, so a handler can
    otherwise act on a command typed minutes ago. Expects a SantaBot method that
    accepts ``(update, context)`` and exposes ``is_update_expired``.
    """

    @functools.wraps(handler)
    async def wrapper(self: Any, update: Any, context: Any) -> Any:
        if self.is_update_expired(update, handler_name=handler.__name__):
            return None
        return await handler(self, update, context)

    return wrapper
