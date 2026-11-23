# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).
While the version is still `0.y.z`, anything may change at any time and breaking
changes are called out but bump the minor version (SemVer §4).

## [0.2.0] - 2026-11-23

This release is not a drop-in replacement for 0.1.0: the configuration file is
gone, the Telegram library was rewritten around async, and the database schema is
now migration-managed. Read *Upgrading from 0.1.0* below before deploying.

### Breaking

- **Configuration is environment-only.** `config/default_config.ini` was deleted.
  The bot now reads `TELEGRAM_BOT_TOKEN` (required), `DATABASE_URL` (AWS Lambda
  entrypoint only; the local entrypoint always uses `bot.sqlite`),
  `MESSAGE_MAX_AGE_SECONDS` (default `60`), and `FEEDBACK_CHAT_ID` (optional).
  `uv run` does not read a `.env` on its own: pass `--env-file .env` or set
  `UV_ENV_FILE`. See `.env.example`.
- **python-telegram-bot 13.x → 22, async only.** Every handler is a coroutine and
  the project requires `python-telegram-bot>=22.0`. The v12-era
  `network_loop_retry` override was removed, along with the v20 transition script.
  Any third-party subclass overriding the old synchronous handler signatures will
  no longer work.
- **Python 3.11 or newer is required** (`datetime.UTC` is used). The dependency
  floor moved through 3.10 and is now `requires-python = ">=3.11"`; the Docker
  image builds on `python:3.13-slim`.
- **SQLAlchemy 2.x, `>=2.1`.** The ORM layer was migrated to 2.0-style mapped
  classes (`Mapped[...]` / `mapped_column`) and to `Session` usage; models,
  repositories, and migrations no longer follow the 1.x declarative idiom.
- **The schema is migration-managed.** Alembic is now a runtime dependency
  and migrations run automatically at startup, for both the
  local and Lambda entrypoints. Existing databases are upgraded in place rather
  than rejected, but a database created by 0.1.0 must pass through the migrations
  before the bot will use it.
- **Schema changes** (all delivered as Alembic revisions):
  `created_at` / `assigned_at` timestamps on the core tables, a new
  `exchange_events` table, a `link.notified_at` column, per-group exchange
  options (`groups.requires_address`, `groups.wishlist_enabled`, `groups.title`),
  wishlists scoped to a group, a `groups.left_at` column, a `feedback` table, and
  the foreign keys the initial schema omitted.
- **Locale directory renamed `pt_br` → `pt_BR`.** Custom deployments that set
  their own locale path or ship hand-placed `.mo` files must update the path.
- **`bot.sqlite` is created with mode `0600`.** It holds mailing addresses; a bot
  previously started as one user and restarted as another may now fail to open it.
  Log files are `0600` for the same reason.
- **Message bodies moved from INFO to DEBUG records**, and the root logger stays
  at INFO, so a log written with default settings no longer contains message
  text. Anything that scrapes `santabot.log` for user text needs the level raised.
  User-controlled fields are logged with `%r`. Rotation is weekly with 52 files
  kept (about a year), triggered on write rather than by a timer.

### Added

- Wishlists, scoped per exchange: `/wish` in a private chat edits a list for a
  group the user has joined, capped at 20 items / 1024 characters per item /
  3500 characters total, and delivered inside the recipient's message when the
  exchange enables it.
- Per-group exchange settings via `/settings` (group admins only): whether the
  delivery message includes the recipient's mailing address
  (`groups.requires_address`), and whether the exchange uses wishlists
  (`groups.wishlist_enabled`). Both default to off for new groups; groups that
  predate the feature were backfilled to `requires_address = 1` so their
  behaviour did not change.
- Wishlist sharing through Telegram inline mode (`InlineQueryHandler`), with a
  share button in `/wish` that pre-fills the current exchange.
- `/feedback`, forwarding a problem report to the private chat named by
  `FEEDBACK_CHAT_ID` (stored in the database when the variable is unset). Reports
  are capped at 3500 characters to stay inside Telegram's 4096-character limit.
- `ExchangeEvent` audit model and migration for exchange lifecycle events.
- Delivery is now resumable: assignments are persisted before any message is
  sent, so a restart mid-delivery resumes the undelivered recipients instead of
  re-pairing or silently skipping them.
- `/status` reports *pending* deliveries rather than only completed ones.
- Groups record `left_at` when the bot loses access to a chat
  (`ChatMemberHandler.MY_CHAT_MEMBER`), so departed groups can be told apart from
  active ones.
- Logging: the reason an expired update was dropped, the PID and log path at
  startup, and wishlist/settings command entry are all recorded.
- i18n: six locales (`de`, `en`, `pt_BR`, `fr`, `it`, `ru`), message catalogs
  preloaded once at startup instead of re-reading the `.mo` per update, and
  whole-sentence msgids replacing concatenated fragments (a translated sentence
  can now be reordered freely).
- Test suite: coverage for pairing logic, handlers, `set_and_send`, the
  `set_pairing` skip branch, and a guard that fails when a registered command is
  missing from `/help`; pre-commit hooks running ruff, mypy, and pytest.
- `.devcontainer` for container-based development.

### Changed

- `bot/` split into repositories, services, models, and entrypoints
  (`cd983b3`, `67bc778`, `c85edb0`); `ExchangeService` is injected rather than
  constructed inside handlers, and the migration config is passed explicitly.
- `BlockedLinks.py` renamed to `BlockedLink.py`; `bot/models/` is imported as a
  package rather than module by module.
- Dependencies are resolved with `uv` (`pyproject.toml` + `uv.lock`), the
  Dockerfile builds with `uv sync --frozen --no-dev`, and the base image moved to
  Python 3.13. `.gitignore` replaced with the canonical Python template.
- Ruff keeps its `E,F,W,I,UP,S` rule set, now targeting Python 3.11, and the
  pre-commit suite fails on deprecation warnings.
- Dependency refreshes: certifi 2026.11.20, pyyaml 6.0.4, virtualenv 21.15.11.
- Documents-only commits: README rewritten around `.env`, installation,
  per-exchange settings, wishlists, inline mode, log retention, and the
  translation workflow; `/help` output documents `/wish` and `/settings`.

### Removed

- `config/default_config.ini` (replaced by environment variables).
- PTB v12-era `overrides/network_loop_retry_override.py`.
- The one-off `v20_code_transition.py` migration script, once the async rewrite
  landed.

### Fixed

- `random.sample()` called with a set raised on Python 3.13; the argument is now
  materialized as a list.
- The initial migration omitted foreign keys present in the models; a later
  revision adds them.
- Model annotations satisfy mypy's strict-optional mode (`Mapped[...]` on every
  guarded attribute).
- Wishlist messages show group names instead of raw chat ids.

### Security

- `bot.sqlite` and `santabot.log` (active and rotated) are created `0600`: both
  can contain mailing addresses.
- User-controlled fields logged with `%r`, and message bodies kept out of INFO
  records.

## [0.1.0] - 2020-11-15

Untagged baseline: the last state pushed to `origin/main` (commit `4ed5809e`,
"starting unit tests"), retroactively numbered to match `pyproject.toml`.

This repository's own history is a rewritten twin of that commit: `5cdda37`
carries the same message, and every commit on the two first-parent chains has an
identical tree (81/81), so the content is the same and only the ids differ. The
tag points at the local twin so the compare link below spans the real diff
instead of two unrelated histories.

No changelog was kept before this entry, so the contents below are not enumerated.
Known properties of that state, from the commits that replaced it: a single
synchronous `SantaBot` class on python-telegram-bot 13.x with v12 compatibility
overrides, configuration in
`config/default_config.ini`, a hand-rolled schema with no migrations, and a
`requirements.txt` install.

## Upgrading from 0.1.0

1. Install Python 3.11+ and `uv`.
2. Create `.env` from `.env.example` and set at least `TELEGRAM_BOT_TOKEN`.
   Launch with `uv run --env-file .env python run.py` — `uv run` alone does not
   read `.env`. Keep a backup of the old `config/default_config.ini` values until
   the bot starts cleanly; the file itself is no longer read.
3. Re-resolve dependencies (`uv sync`) — python-telegram-bot jumps 13.x → 22 and
   SQLAlchemy to 2.x. Custom subclasses of the old handlers need rewriting as
   coroutines.
4. Back up the database. Migrations run at startup and startup never reverts
   them; keep the copy until the bot answers `/status`.
5. If you ship your own catalogs, move `pt_br` to `pt_BR` and recompile with
   `pybabel compile` (see `bot/locale/README.md`).
6. Re-check file ownership: `bot.sqlite` and `santabot.log` are now `0600`.
7. If you use inline wishlist sharing, enable inline mode once in BotFather
   (`/setinline`) with the placeholder `wishlist`.

[0.2.0]: https://github.com/Voxter256/Secret-Santa-Bot/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Voxter256/Secret-Santa-Bot/releases/tag/v0.1.0
