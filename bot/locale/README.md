From root directory

```
uv run pybabel extract . -o bot/locale/messages.pot \
  --project "Secret-Santa-Bot" --version "1" \
  --copyright-holder "John Elgin" \
  --msgid-bugs-address "Voxter.256@gmail.com" \
  --last-translator "John Elgin <Voxter.256@gmail.com>" \
  --header-comment '# Secret-Santa-Bot translations.
# This file is distributed under the same license as the Secret-Santa-Bot project.
# John Elgin <Voxter.256@gmail.com>, 2020.
#'
```

```
uv run pybabel update -i bot/locale/messages.pot -d bot/locale
uv run pybabel init -i bot/locale/messages.pot -l {language} -d bot/locale
uv run pybabel compile -d bot/locale/
```

Notes

- The options are required. `pybabel extract` reads no metadata from `pyproject.toml`,
  `setup.cfg` or `babel.cfg`; without them the header is filled with the placeholders
  `PROJECT VERSION`, `EMAIL@ADDRESS`, `FULL NAME <EMAIL@ADDRESS>`, `ORGANIZATION`.
- `--project` cannot be empty: an empty value falls back to `PROJECT`. The historical
  `Project-Id-Version:  1` (blank project name) was hand-edited and is not reproducible.
- `Language-Team` has no `pybabel extract` option. It stays `LANGUAGE <LL@li.org>` in the
  template and must be set per locale in `*/LC_MESSAGES/messages.po`.
- `pybabel update` does not copy the template header into existing `.po` files (only
  `POT-Creation-Date`), but it rewrites them as LF and appends `;` to `Plural-Forms`, so
  expect whole-file diffs on the CRLF catalogs.
- Babel is in the `dev` dependency group, so `uv run` uses the version from `uv.lock`.
