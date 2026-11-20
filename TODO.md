# TODO

## Housekeeping

- [ ] Remove stale artifacts: `config/` directory (dead after env var switch), `santabot.log` (3.9MB), `bot.sqlite` (212KB), `santabot old.log`
- [x] Remove `download` artifact accidentally committed in `zxqvyzny` — file purged from history
- [x] Review `v20_code_transition.py` — kept as reference, remove once migration is stable
- [ ] Rename `bot/models/BlockedLinks.py` — table name is misspelled (plural, inconsistent)
- [ ] Move `status_query.sql` or remove from repo root

## Testing

- [ ] Add unit tests for core pairing logic: `find_combination`, `get_random_pairing`
- [ ] Add tests for message handler flows: `join`, `leave`, `not`, `allow`, `status`
- [ ] Add tests for `set_and_send_individual_result`
- [ ] Add integration test for the start → join → exchange flow

## Build

- [x] Verify Docker build works with updated Dockerfile (Python 3.13 + uv)

## Future

- [ ] Replace `Bot(token)` + `Application.builder().bot(bot)` in LambdaSantaBot with `Application.builder().token(token)` pattern
- [ ] Add persistent issue tracker (GitHub Issues or similar)
- [x] Add pre-commit hooks (lint, type-check, test)