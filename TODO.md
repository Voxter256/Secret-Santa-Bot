# TODO

## Migrations

- [x] Bootstrap Alembic: 4 revisions matching current schema (`initial_schema`, `add_timestamps`, `add_exchange_events`, `add_link_notified_at`)
- [x] Call `run_migrations()` from both entrypoints in `run.py` — `__main__` and `lambda_handler`
- [x] Move `alembic` from the dev group to `[project].dependencies` — the image installs with `uv sync --no-dev`, so `bot._migrate` previously raised ImportError at startup
- [x] Replace `DBConnection.createAll()` in `tests/test_santa_bot.py` with `run_migrations()` — tests build their schema from the real migrations on a per-test in-memory SQLite database, and `TestSchemaFromMigrations` asserts the table set plus the recorded head revision
- [x] Delete `DBConnection.createAll()` / `dropAll()` once tests no longer use them — removed with the now-unused `Base` import
- [x] Resolve `alembic.ini` by an absolute path anchored to the app root — `bot/_migrate.py` now uses `ALEMBIC_INI = Path(__file__).parent.parent / "alembic.ini"`; verified by running migrations from `/tmp`
- [x] Migrate through an existing connection for in-memory SQLite — `run_migrations(db_url, connection=...)`, `alembic/env.py` honours `config.attributes["connection"]`, `DBConnection` holds a `StaticPool` for `sqlite://`
- [ ] Run migrations against MySQL — only SQLite has been executed (tests use `sqlite://` with a shared StaticPool connection, compose default is `sqlite:///bot.sqlite`)

## Exchange delivery

- [x] Persist the pairing before messaging anyone — `LinkRepository.set_pairing()` commits the whole pairing atomically, so a failed send no longer rolls back assignments that were already delivered
- [x] Track per-link delivery with `links.notified_at` + migration `60e6fe52a838`
- [x] Keep delivering past unreachable participants (`Forbidden` / `BadRequest`) and report them by `@username`
- [x] Let `/start_exchange` resume only the undelivered links instead of replying "The exchange has already been setup!"
- [x] Clear `receiver_id`, `assigned_at` and `notified_at` on `/reset_exchange`
- [x] `/status` must report pending deliveries instead of "The exchange has finished" — `get_exchange_status()` now returns `delivery_pending` when receivers exist but any link lacks `notified_at`; the handler names the undelivered participants and points at `/start_exchange`
- [ ] Add `.po` entries for the admin string `Could not message: {names}. …` — it currently renders in English for every locale
- [x] Test the `set_pairing()` skip branch — `test_assign_pairing_skips_santas_without_link`: a santa id in the pairing with no `links` row is skipped without raising, while the existing link still gets its `receiver_id` and `assigned_at`

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
- [x] Add tests for the exchange delivery paths (10): marks `notified_at`, continues past a `Forbidden` santa, treats `BadRequest` as unreachable, second run sends nothing, missing receiver, pairing survives a failed delivery, `/start_exchange` resumes pending, already-delivered short-circuit, `/reset_exchange` clears state, username fallback
- [x] Cover translation preloading and locale resolution (`tests/test_translations.py`, 3 tests) — catalogs load once at construction, de/ru/pt-BR resolve, unknown and `None` fall back to English
- [x] Run the suite without `PYTHONPATH=/workspace` — `pythonpath = ["."]` in `[tool.pytest.ini_options]`; 78 tests collected
- [x] Fix the 24 mypy errors so the pre-commit mypy hook passes — models annotated with `Mapped[...]`/`mapped_column()`, matching the nullability in the migrations; verified `mypy` clean across 24 files and no schema drift against a migrated database
- [ ] Add integration test for the start → join → exchange flow

## Build

- [x] Verify Docker build works with updated Dockerfile (Python 3.13 + uv)
- [x] Drop `--override-ini="python_files=Test*.py"` from the pre-commit pytest hook — after the test module rename it collected zero tests

## Future

- [ ] Replace `Bot(token)` + `Application.builder().bot(bot)` in LambdaSantaBot with `Application.builder().token(token)` pattern
- [ ] Add persistent issue tracker (GitHub Issues or similar)
- [x] Add pre-commit hooks (lint, type-check, test)
