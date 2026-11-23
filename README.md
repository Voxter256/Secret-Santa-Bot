## Synopsis

This is a bot for Telegram written in Python made to manage a group's Secret Santa Exchange. It is unique from other bots that I found in that it is centrally managed through a group chat, with private messages for addresses and results. When deployed it will be available at @GroupSecretSantaBot

## Code Example

`/join`  
Joins the Secret Santa Exchange in this chat group

`/not @MySO`  
Prevents you from being assigned a Santa to people you're already getting gifts for outside this exchange

`/start_exchange`  
Finds every possible combination that doesn't have you picking yourself or anyone selected with `/not`, randomly selects one, then sends each participant a private message with their username and address

## Motivation

Christmas can be stressful if you have to find gifts for everyone all within your budget. I've been in Secret Santa's where a third party can't participate, instead mediating the event. Odds are good that names will be drawn multiple times because of conflicts. This is meant to simply the process, especially in larger groups.

## Installation

Requires Python 3.10+ (PEP 604 annotations are evaluated at class-definition time) and [uv](https://docs.astral.sh/uv/).

    uv sync
    export TELEGRAM_BOT_TOKEN="<token from @BotFather>"
    uv run python run.py

Or keep the settings in a file instead of the shell:

    uv sync
    uv run --env-file .env python run.py

`uv run` reads a `.env` in the project directory by default, so the flag is only needed to point at a different file; `--no-env-file` turns it off entirely.

The first run creates `bot.sqlite` when it is missing and applies the Alembic migrations before the bot starts, so an existing database is upgraded rather than rejected.

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | required | Token from @BotFather. |
| `MESSAGE_MAX_AGE_SECONDS` | `60` | Updates older than this are discarded, so a restart does not act on messages queued while it was down. |
| `DATABASE_URL` | unset | Database used by the AWS Lambda entrypoint. The local entrypoint (`run.py`) uses `bot.sqlite` in the working directory and ignores it. |

### Docker

    docker compose up --build

`docker-compose.yaml` bind-mounts the working tree into the container and passes the same variables through. Put `TELEGRAM_BOT_TOKEN` in `.env` first.

### Dependencies

Runtime: `python-telegram-bot`, `SQLAlchemy`, `Alembic`, and `mysql-connector-python` for non-SQLite deployments. Development adds `pytest`, `ruff`, `mypy`, `pre-commit`, and `Babel`; `pre-commit install` wires the hooks that run before every commit.

### Translations

Catalogs live in `bot/locale/<lang>/LC_MESSAGES/`. Both the `.po` sources and the compiled `.mo` files are committed, so a string change needs the catalog recompiled with Babel before it takes effect.

### Logs

`santabot.log` is written in the working directory and rotates weekly, keeping 52 files — about a year. Rotation is triggered by a write rather than a timer, so an idle bot keeps its last file. The active and rotated files are created `0600`.

## API Reference

###### All Users

`/help`  
Shows this list of commands.

`/start`  
Sent only in a private message to begin personal setup.

`/hello`  
Sent only in a group chat to enable the gift exchange.

`/settings`  
Sent only in a group chat by an admin to choose what this exchange requires.

`/address`  
Sent only in a private message to show and update your optional mailing address.

`/wish`  
Sent only in a private message to edit your wishlist for an exchange you have joined.

`/join`  
Joins you in the gift exchange in this chat.

`/status`  
Gets the status of this chat's exchange.

`/not @Mention`  
Prevents you from being paired up with this participant.

`/allow @Mention`  
Removes block that was preventing you from being paired up with this participant.

`/leave`  
You will leave the gift exchange in this chat.

`/start_exchange`  
Begins the gift exchange by assigning a recipient to every participant, then messaging them privately the details. When the wishlist is enabled and someone has no items, it names them and stops; `/start_exchange confirm` starts anyway.

`/reset_exchange`  
Resets the gift exchange by removing every participant's assigned recipient.

## Exchange settings

Both options are off by default and are toggled per group with `/settings`, by a group admin:

- **Address required** — when on, the delivery message includes the recipient's mailing address. Groups that existed before this option was added were backfilled to on, so their behaviour did not change; new groups start with it off.
- **Wishlist** — when on, participants can keep a wishlist for this exchange and the delivery message includes the recipient's items.

Wishlists are scoped to a single exchange, so the same person can keep different lists for different groups. They are edited in a private chat with `/wish` and are never posted to the group by the bot. Limits: 1024 characters per item, 20 items, 3500 characters in total — the total is what keeps a list deliverable inside Telegram's 4096-character message limit.

### Sharing a wishlist

Wishlists can be shared through Telegram inline mode: type the bot's username in any chat and pick an exchange. Inline mode has to be enabled once in BotFather:

    /setinline

with a placeholder of `wishlist`. The same value can be set later with `setMySettings` and `inline_query_placeholder`. The share button in `/wish` pre-fills the query with that exchange, so the picker shows a single result.


## Contributors

I'm currently tracking issues here in GitHub. I encourage feature suggestions as well as code improvement! There is plenty of work that needs done

## License

MIT License per LICENSE.txt
