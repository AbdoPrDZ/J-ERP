# Workflows

All commands run from the project root.

## Prerequisites

- PostgreSQL reachable with the credentials in `jerp.config.json` (or
  `JERP_DB_*` overrides).
- Python 3.15 virtual environment at `.venv` with `requirements.txt` installed.
- Node.js + npm for the frontend and module view builds.

## Run

```text
python app.py                 # http://127.0.0.1:1347
python app.py --port 9000     # override the configured port
python app.py -v              # debug logging
```

No database is selected on first run. Create or choose one in the UI
(`/db/manager`); if exactly one database exists, `/` selects it automatically.

## Frontend Development

```text
python app.py                 # backend on the configured port
npm run dev                   # Vite dev server on 5173, proxies to the backend
```

The dev plugin reads `GET /__endpoints` to build its proxies; `/` is handed to
the backend so login/database redirects still work.

## Build

```text
npm run typecheck             # tsc -b
npm run build                 # tsc -b + vite build + shared React runtime -> data/ui
npm run build:runtime         # only data/ui/react-runtime.js
npm run build:views           # module view bundles -> data/view/<module>
npm run build:all             # build + build:views
```

`data/` is generated and gitignored. Rebuild it; never edit it by hand.

## Create A Database

Use the database manager UI (or `POST /api/databases`). Creation installs the
core module, seeds an admin user, and requires an admin password. The name must
match `^[a-z_][a-z0-9_]{0,62}$`.

## Install / Update / Uninstall A Module

1. The module directory must contain `configure.json` with `name`, `version`,
   `summary`, and optionally `depends`, `logo`, `routes`.
2. Install/update from the Modules page (virtual `module` model) or by calling
   `module.install` / `module.update` through the model API.
3. Install runs schema sync for the module's models, records it in `sys_module`,
   and builds its views with `node tools/build-views.mjs <module>` when Node is
   available.
4. `core` cannot be uninstalled; modules with dependents cannot be uninstalled.
5. Uninstall drops the module's tables — confirm with the user first.

## Add A Model

1. Create `modules/<module>/models/<name>.py`:
   subclass `jerp.models.Model`, set `_table`, declare `jerp.fields.*`.
2. Import it from `modules/<module>/models/__init__.py` (or the package
   `__init__`) so the metaclass registers it.
3. Install or update the module so the schema is synchronized.
4. Expose custom behavior with `@jerp.api_expose`; it is then callable at
   `POST /api/model/<model>/<method>`.

## Add A Field

Declare the field and update the module. The syncer adds the column and records
it in `sys_field`. If the field replaces an existing column, the syncer may
infer a rename; a genuinely removed field drops its column and its data.

## Add A Page / View

1. Add `modules/<module>/ui/src/views/<Name>.tsx` with a default-exported React
   component; import UI primitives from `@jerp/ui`.
2. Build views (`npm run build:views` or module install/update). The view key is
   `<module>.<snake_case_file>`.
3. Declare it in `configure.json` `routes`:
   `{"label": "…", "view": "<module>.<key>", "endpoint": "/optional", "sequence": n}`.
4. Groups are entries with `label` + `children`; `hide` removes it from the menu;
   `auth: false` makes it public; `header: false` hides the shell header.
5. Restart the backend so page routes are re-registered.

## Verify Changes

There is no test suite or lint configuration in the repository. At minimum:

- `npm run typecheck` for TypeScript changes.
- Rebuild the UI (`npm run build`) after changing the shell/UI kit.
- Start `python app.py` and exercise the affected page/API against a test
  database.
- For backend-only edits, an import/compile check (e.g. `python -m compileall`)
  catches syntax errors.

Do not commit or push; leave changes in the working tree until asked.
