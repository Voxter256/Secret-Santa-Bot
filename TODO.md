# TODO

## Migrations

- [x] Bootstrap Alembic: 3 revisions matching current schema (`initial_schema`, `add_timestamps`, `add_exchange_events`)
- [x] Call `run_migrations()` from both entrypoints in `run.py` — `__main__` and `lambda_handler`
- [x] Move `alembic` from the dev group to `[project].dependencies` — the image installs with `uv sync --no-dev`, so `bot._migrate` previously raised ImportError at startup
- [ ] Replace `DBConnection.createAll()` in `tests/TestSantaBot.py:23` and `:159` with `run_migrations()` — tests currently build the schema from `Base.metadata`, so no test exercises the migrations
- [ ] Delete `DBConnection.createAll()` / `dropAll()` once tests no longer use them
- [ ] Resolve `alembic.ini` by an absolute path anchored to the app root — `Config("alembic.ini")` in `bot/_migrate.py` is cwd-relative
- [ ] Run migrations against MySQL — only SQLite has been executed (tests use `sqlite:///:memory:`, compose default is `sqlite:///bot.sqlite`)

## Housekeeping

- [x] Remove `config/` directory (dead after env var switch) — confirmed absent
- [ ] Remove `santabot.log` (3.8 MB) and `santabot old.log` (20 KB)
- [ ] Decide on `bot.sqlite` (272 KB) — integration fixture or repo artifact
- [x] Remove `download` artifact accidentally committed in `zxqvyzny` — file purged from history
- [x] Review `v20_code_transition.py` — removed from the repo
- [x] Rename `bot/models/BlockedLinks.py` → `BlockedLink.py` — filename was plural, inconsistent with other model files
- [ ] Move `status_query.sql` (380 B, dated 2019) out of the repo root or remove it

## Testing

- [x] Add unit tests for core pairing logic: `find_combination`, `get_random_pairing`
- [x] Add tests for message handler flows: `join`, `leave`, `not`, `allow`, `status`
- [x] Add tests for `set_and_send_individual_result`
- [ ] Add integration test for the start → join → exchange flow
- [ ] Run the suite without `PYTHONPATH=/workspace` — plain `uv run pytest` fails collection with `ModuleNotFoundError: No module named 'bot'` because the lock records the project as `source = { virtual = "." }` and it is not installed into the venv

## Build

- [x] Verify Docker build works with updated Dockerfile (Python 3.13 + uv)

## Future

- [ ] Replace `Bot(token)` + `Application.builder().bot(bot)` in LambdaSantaBot with `Application.builder().token(token)` pattern
- [ ] Add persistent issue tracker (GitHub Issues or similar)
- [x] Add pre-commit hooks (lint, type-check, test)
