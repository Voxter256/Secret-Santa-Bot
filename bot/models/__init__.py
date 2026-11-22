"""ORM model package.

Importing this package registers every table on ``bot.Base.Base.metadata``,
which is what Alembic's ``autogenerate`` compares against.  Alembic's
``env.py`` therefore imports this package rather than each module, so a new
model only has to be added here.

Reference the classes from their own modules
(``from bot.models.Group import Group``) to keep import graphs obvious.
"""

from bot.models.BlockedLink import BlockedLink
from bot.models.ExchangeEvent import ExchangeEvent
from bot.models.Group import Group
from bot.models.Link import Link
from bot.models.Participant import Participant
from bot.models.WishlistItem import WishlistItem

__all__ = [
    "BlockedLink",
    "ExchangeEvent",
    "Group",
    "Link",
    "Participant",
    "WishlistItem",
]
