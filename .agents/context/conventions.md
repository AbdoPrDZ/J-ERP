# Conventions

## Formatting (enforced by `.editorconfig`)

- UTF-8, LF line endings, final newline, no trailing whitespace.
- 2-space indentation everywhere (Python and TypeScript/TSX).

## Python

- Target Python 3.15; start framework modules with
  `from __future__ import annotations`.
- Single quotes for strings; absolute imports (`from jerp... import ...`,
  `from modules... import ...`).
- Framework modules carry a module docstring explaining responsibility.
- Classes are PascalCase; functions/variables snake_case. Model classes are
  PascalCase, tables plural snake_case, field attributes snake_case.
- Prefer small, explicit helpers over framework magic; lazy imports are used at
  call sites to avoid circular imports (`jerp.env` ↔ `jerp.models`).
- Raise `ValueError`/`RuntimeError` with clear messages; HTTP handlers return
  `response.json({...}, status=...)` instead of raising.
- User-facing Python messages use `_t('key', 'English source', **params)` from
  `jerp.i18n`. Models carry a short `_description`; field labels/help are
  translated from model keys.
- SQL identifiers go through `jerp.dialect.quote_ident`/`quote_table`; values
  are always parameterized (`%s`).

## TypeScript / React

- 2 spaces, single quotes, semicolons; functional components with hooks.
- Tailwind utility classes for styling; no separate CSS files for module views.
- Module views import primitives from `@jerp/ui` — never by relative path into
  `jerp/ui`. React is resolved through the import map.
- A view file's default export is the component; the view key is derived from
  the file name.
- Shared kit additions belong in `jerp/ui/src/core/` and must be re-exported
  from `runtime.ts` to reach modules.
- User-facing UI strings use `t('view.<module>.<view>.<key>')` from
  `@jerp/locale`. There is no fallback argument; add the English value to
  `i18n/en.lang` and run `i18n check`. The database manager page stays
  English-only because it renders before a database/catalog exists.
- Dynamic keys used through variables belong in `CORE_EXTRA_KEYS` or
  `MODULE_EXTRA_KEYS` in `jerp/i18n_cli.py` so scaffolding still collects them.

## Boundaries

| Change | Location |
|---|---|
| Framework/model/schema/HTTP behavior | `jerp/` |
| Business features, pages, controllers | `modules/<name>/` |
| Build scripts and dev tooling | `tools/` |
| Built UI, built views, uploads | `data/` (generated, gitignored) |

Never put module-specific behavior in the framework, and never edit generated
output in `data/`.

## Configuration

- Paths in `jerp.config.json` are relative to the working directory; run from
  the project root.
- Use environment overrides (`JERP_DB_*`, `JERP_APP_*`) for machine-specific or
  secret values instead of editing committed defaults.

## Security And Data Safety

- Passwords are hashed with PBKDF2-SHA256 (`jerp.security`); never store or log
  plaintext. Do not weaken the iteration count or comparison.
- Uploaded files are only served when registered in the database's `files`
  table; keep that check.
- Path traversal is blocked in static/asset/storage serving; keep resolving and
  validating paths before reading files.
- Schema changes keep removed columns (retired) and refuse lossy type changes;
  dropping a column needs `allow_drop=True` (database-wide), and module uninstall
  drops tables. Preview first (`module.preview`, `update --dry-run`, `doctor`)
  and confirm destructive operations with the user. Ordinary requests never
  retype or drop columns; only an explicit install/update does.
- `jerp.config.json` currently contains development credentials; do not commit
  real secrets. Use `JERP_DB_ADMIN_USER` / `JERP_DB_ADMIN_PASSWORD` for the
  optional force-drop role rather than committing a superuser password.
- Deleting a referenced record is blocked by the ORM; do not bypass it with raw
  SQL in controllers without an explicit reason.

## Verification

- `npm run typecheck` for TypeScript changes.
- `npm run build` after shell/UI-kit changes; `npm run build:views` after view
  or menu-config changes (it validates declared views).
- `python -m unittest discover -s tests` for the unit suite.
- `python -m jerp.cli i18n check` after translation changes.
- Start the app and exercise the affected flow.
- Draft/compute/onchange changes should also be exercised through a temporary
  database (draft create → change → commit).

## Git And Change Management

- Do not commit, push, tag, change branches, or open pull requests unless the
  user explicitly asks.
- Do not initialize a repository or alter Git configuration.
- Keep unrelated changes out of the current task.
