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

The dev plugin reads `GET /__endpoints` to build its proxies and, for each HTML
request, `GET /__modules` with the browser's `jerp_db` cookie so only the
selected database's installed modules appear. With no database (or with the
backend down) it exposes `core` only. Restart Vite after changing
`vite.config.ts` or `tools/vite-plugin-jerp.mjs`.

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
   `module.install` / `module.update` through the model API. The Modules page
   previews the plan (`module.preview`) before updating and offers the
   database-wide `allow_drop` option behind a destructive confirmation.
3. Install runs schema sync for the module's models, records it in `sys_module`,
   and builds its views with `node tools/build-views.mjs <module>` when Node is
   available.
4. `core` cannot be uninstalled; modules with dependents cannot be uninstalled.
5. Uninstall drops the module's tables — confirm with the user first.
6. Menus and `add_to_home` entries are read from the database per request, so
   they disappear after a refresh; restart the backend if Python modules changed.

CLI equivalents (preview first):

```text
python -m jerp.cli --database <db> update --dry-run      # plan, no DDL
python -m jerp.cli --database <db> update                # apply safe changes
python -m jerp.cli --database <db> update --allow-drop   # destructive
python -m jerp.cli --database <db> doctor [--sql]        # retired columns (+ SQL)
```

`--dry-run` exits nonzero when the plan is blocked. A real update prints the
applied plan; blocked changes make it exit nonzero after the safe part commits.

## Add A Model

1. Create `modules/<module>/models/<name>.py`:
   subclass `jerp.models.Model`, set `_name`/`_table`, declare `jerp.fields.*`.
2. Import it from `modules/<module>/models/__init__.py` (or the package
   `__init__`) so the metaclass registers it.
3. Install or update the module so the schema is synchronized.
4. Expose custom behavior with `@jerp.api_expose` (instance methods receive the
   record selected by `id`); it is callable at
   `POST /api/model/<model>/<method>`.

## Add A Field

Declare the field and update the module. The syncer adds the column and records
it in `sys_field`. Renaming a field requires `renamed_from='old_attribute'` on
the new field; without it the old column is kept as retired and the new field
starts empty. The request path applies declared renames automatically but defers
type changes to an explicit update. A removed field keeps its column and is
marked `state='retired'`; dropping it requires `allow_drop=True` through
`SchemaSyncer` or `update --allow-drop` (database-wide; inspect with `doctor`
first).

For Odoo-style fields:

```python
price = fields.FloatField(name='Unit price')
subtotal = fields.FloatField(name='Subtotal', compute='_compute_subtotal')

@depends_on(['quantity', 'price_unit'])
def _compute_subtotal(self):
  for line in self:
    line.subtotal = (line.quantity or 0) * (line.price_unit or 0)

@on_change(['product_id'])
def _on_change_product_id(self):
  for line in self:
    line.price_unit = line.product_id.price if line.product_id else 0
```

Instance-style `@on_change` handlers and classmethod handlers returning a values
dictionary are both supported. Computed fields are read-only in forms.

## Add A Page / View

1. Add `modules/<module>/ui/src/views/<Name>.tsx` with a default-exported React
   component; import UI primitives from `@jerp/ui`.
2. Build views (`npm run build:views` or module install/update). The view key is
   `<module>.<snake_case_file>`; nested files such as `views/pages/Home.tsx` map
   to `<module>.home`.
3. Declare it in `configure.json` `routes`:
   `{"label": "…", "view": "<module>.<key>", "endpoint": "/optional", "sequence": n}`.
4. Groups are entries with `label` + `children`; `hide` removes it from the menu;
   `auth: false` makes it public; `header: false` hides the shell header.
5. Add `"add_to_home": true` (and an optional `description`) to show it in the
   Home quick-access grid. Groups and hidden pages are supported.
6. Restart the backend so page routes are re-registered. `build:views` fails if
   a declared menu view has no matching view file.

## Verify Changes

There is no linter configured. At minimum:

- `npm run typecheck` for TypeScript changes.
- Rebuild the UI (`npm run build`) after changing the shell/UI kit.
- `npm run build:views` after view/manifest changes (it also validates that every
  declared menu view has a file).
- `python -m unittest discover -s tests` for the unit suite.
- Start `python app.py` and exercise the affected page/API against a test
  database.
- For backend-only edits, `python -m compileall jerp modules` catches syntax
  errors.

Do not commit or push; leave changes in the working tree until asked.
