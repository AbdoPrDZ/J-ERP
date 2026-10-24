# J-ERP

**A modular, self-hosted ERP framework where modules own everything — models, schema, menus, pages and views.**

J-ERP pairs a small declarative Python ORM over PostgreSQL with a React 19 + TypeScript + Tailwind SPA. Modules are installed **per database**: installing or updating a module synchronizes its schema in a single transaction, so there are no migration files to write or maintain. Each module also ships the menus, routes and views it contributes, which the server injects into the shell and the client loads dynamically.

[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.15-3776AB.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/react-19-61DAFB.svg)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/postgresql-%3E%3D14-4169E1.svg)](https://www.postgresql.org/)

---

## Highlights

- **Per-database modules** - one server, many independent databases, each with its own set of installed modules and its own schema.
- **No migrations** - models are declared in Python; the schema is diffed and synchronized transactionally on install/update.
- **Odoo-style models** - positional relation/selection fields, recordsets, many2one record access, one2many commands, computed fields with `@depends_on` and server-side `@on_change`.
- **Server-side drafts** - forms and embedded tables edit `temp.model` drafts with a debounced on-change round-trip, reload-safe state and atomic parent/child commit.
- **Multi-database management** - create, list, select and drop databases from the UI; access is scoped to the configured owner.
- **Database-backed navigation** - each module declares routes in `configure.json`; its menu entries are synchronized into `sys.menu` on install/update and served by `GET /api/menu`.
- **SPA shell** - menu/internal navigation uses the History API, animated drawer/view transitions and a shared loading indicator instead of full page reloads.
- **Declarative page DSL** - compose pages from `Page`, `Table`, `Cards`, `Form`, `FormTable`, `FormField`, `FormGroup`, `Action` and friends; no per-view plumbing.
- **Typed model API** — a single endpoint (`POST /api/model/<model>/<func>`) plus a typed client, instead of hand-written controllers for every screen.
- **Views built on install** — module view bundles are compiled with esbuild into `data/view/<module>/` and loaded through an import map.
- **Files and images** — two-step uploads, a `File` model, `FileField`/`ImageField` widgets, and storage served only for files known to the active database.
- **Auth included** — users with hashed passwords (PBKDF2), hidden fields that never leave the server, and login/profile pages.
- **Database-backed i18n** — per-user language preference, flat `.lang` catalogs, server/UI translation, Google-assisted CLI and activation-time loading.
- **Safe deletion** — records referenced by many2one/file fields cannot be deleted; database drops close app sessions and can use an optional admin role for `WITH (FORCE)`.

## Architecture

```
app.py                  HTTP entrypoint (host/port from jerp.config.json)
jerp/                   Framework: ORM, schema sync, router, server, views, modules
  models.py             Model metaclass, recordsets, CRUD, computed fields, drafts
  fields.py             Field types (char, text, int, float, date, file, image, password, …)
  api.py                Decorators: api_expose, on_change, depends_on
  schema.py             Declarative schema synchronization
  modules.py            Module discovery, install/update/uninstall, build hooks
  views.py              Route/view collection and shell rendering
  menus.py              sys.menu synchronization and tree loading
  i18n.py               Language resolution, catalogs and translation
  translate.py          Google Translate client for the i18n CLI
  server.py             HTTP dispatch, static + asset + storage routes
  ui/                   Shared React runtime/SPA shell, page DSL and widgets
modules/<name>/         Feature modules (models, controllers, views, assets)
  configure.json        Module metadata, menus/routes, dependencies
tools/                  Vite plugin and build scripts
tests/                  Unit tests (python -m unittest discover -s tests)
public/                 Vite HTML entry and favicon
data/                   Generated: built UI, view bundles, uploads (git-ignored)
```

## Requirements

- Python 3.15
- PostgreSQL 14 or newer
- Node.js 20 or newer (build tooling only)

## Quickstart

```bash
# 1. Python dependencies
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt

# 2. Frontend build
npm install
npm run build:all

# 3. Run
python app.py                    # http://127.0.0.1:1347
```

Then open <http://127.0.0.1:1347> → **Databases** → create a database (admin username + password). Creating a database automatically installs the `core` module; modules such as `stock` can be installed from **Configuration → Modules**.

Nothing is created at startup — no default database, no implicit schema. The PostgreSQL role used to create databases is controlled by `databases.user` / `databases.owner` in `jerp.config.json`.

### Development

```bash
python app.py        # backend on :1347
npm run dev          # Vite dev server on :5173 with HMR
```

The Vite dev server discovers API/asset/storage proxies at startup by calling the backend's `GET /__endpoints`. It also asks `GET /__modules` for each HTML request (using the browser's `jerp_db` cookie) so only modules installed in the selected database appear. Restart Vite after changing `vite.config.ts` or `tools/vite-plugin-jerp.mjs`.

### Useful commands

```bash
python app.py --port 9000            # override the port
python app.py --host 0.0.0.0         # expose on the network
npm run typecheck                    # tsc -b
npm run build                        # UI shell + shared runtime -> data/ui
npm run build:views                  # module view bundles -> data/view
npm run build:all                    # both
python -m unittest discover -s tests # unit tests
python -m jerp.cli install stock --database <db>
python -m jerp.cli update --database <db>
python -m jerp.cli i18n scaffold --module core --lang ar
python -m jerp.cli i18n check
python -m jerp.cli --database <db> i18n import
```

### Translations

Module translations live in `modules/<module>/i18n/<lang>.lang` as flat
`key = value` files:

```ini
# English: Modules
view.core.modules.title = الوحدات
```

Use the CLI to scaffold every model/view/menu key for a language, check the
files, or load them into `sys.translation`:

```bash
python -m jerp.cli i18n scaffold --module core --lang ar
python -m jerp.cli i18n check
python -m jerp.cli i18n translate --module core --lang ar
python -m jerp.cli --database <db> i18n import --module core --lang ar
```

`i18n translate` works on one module/language pair per run and fills blank
values with Google Translate. Set
`GOOGLE_TRANSLATE_API_KEY` for the official Cloud Translation API, or omit it to
use the public endpoint. Use `--dry-run` to preview and `--overwrite` to replace
existing translations. Install/update also imports the files (file values win).
New databases start with **English only** active. Activate French or Arabic (or
another language) from the Languages page; activating it imports that language's
`.lang` files for all installed modules. Module install/update only imports
currently active languages. The selected language is stored per user in
`sys.user.lang_id`, with the `jerp_lang` cookie as the anonymous/session
fallback. The user menu switches language and reloads.

UI strings use `t('view.<module>.<view>.<key>')` from `@jerp/locale` and have no
inline fallback text; keep the English value in `i18n/en.lang`. Python-facing
errors use `_t('error.<name>', 'English text', **params)`. `i18n scaffold`
collects model/field/description keys, menus, module summaries, Python `_t()`
calls and UI `t()` calls.

## Configuration

`jerp.config.json`:

| Key | Meaning |
| --- | --- |
| `databases.host` / `port` / `user` / `password` / `sslmode` | PostgreSQL connection settings |
| `databases.owner` | Only databases owned by this role are listed (defaults to the connecting user) |
| `databases.admin_user` / `admin_password` | Optional superuser used only to force-drop databases (or use `JERP_DB_ADMIN_USER` / `JERP_DB_ADMIN_PASSWORD`) |
| `app.host` / `app.port` | HTTP bind address (default `127.0.0.1:1347`) |
| `database` | Optional default database for standalone `Environment()` / `JERP_DATABASE` |
| `modules_path` | Where modules are discovered (`modules`) |
| `schema` | PostgreSQL schema used for tables (`public`) |
| `ui_dist` | Built UI directory (`data/ui`) |
| `views_dir` | Built module view bundles (`data/view`) |
| `uploads_dir` | Uploaded files (`data/uploads`) |

Database deletion closes the application's own sessions. If pgAdmin/a
superuser session remains, close it or configure `databases.admin_user` /
`admin_password` (prefer the environment variables) so deletion can use
`DROP DATABASE ... WITH (FORCE)`. The database manager page itself stays in
English because it renders before a database/language is selected.

## Writing a module

A module is a directory under `modules/` containing a `configure.json`:

```json
{
  "name": "stock",
  "version": "1.0.0",
  "depends": ["core"],
  "routes": [
    {
      "label": "Stock",
      "sequence": 30,
      "children": [
        { "label": "Products", "view": "stock.products", "params": { "view": "list" }, "sequence": 1 }
      ]
    }
  ]
}
```

Route entries accept `label`, `view`, `endpoint`, `params`, `sequence`, `img`, `description`, `auth`, `header`, `menu`, `drawer`, `hide` and nested `children`. `sequence` orders the navigation tree; `auth` defaults to `true`. Labelled entries are synchronized into `sys.menu` when the module is installed or updated.

Models are plain Python classes:

```python
from jerp import fields, models


class Product(models.Model):
  _name = 'stock.product'
  _description = 'Products available for sale and stock.'

  name = fields.StringField(name='Name', required=True)
  standard_price = fields.FloatField(name='Cost', default=0.0)
  price = fields.FloatField(name='Price', default=0.0)
  image = fields.ImageField(name='Image')
```

Computed fields and server-side on-change use decorators:

```python
from jerp import fields, models
from jerp.api import depends_on, on_change


class SaleOrderLine(models.Model):
  _name = 'sale.order.line'

  quantity = fields.FloatField(name='Quantity', default=1.0)
  price_unit = fields.FloatField(name='Unit price', default=0.0)
  subtotal = fields.FloatField(name='Subtotal', compute='_compute_subtotal')

  @on_change(['product_id'])
  def _on_change_product_id(self):
    for line in self:
      line.price_unit = line.product_id.price if line.product_id else 0.0

  @depends_on(['quantity', 'price_unit'])
  def _compute_subtotal(self):
    for line in self:
      line.subtotal = (line.quantity or 0.0) * (line.price_unit or 0.0)
```

Records are recordsets: `search`/`browse` return a list-like `RecordSet`, many2one access returns the related record, and reverse one2many attributes (`order.lines`) are discovered automatically. In Python, `Model.new()` returns an in-memory record and `record.save()` writes it with its children in one transaction; with a token, `new` returns a server-side draft instead.

### Schema changes

There are no migration files: the schema is synchronized from the declared fields when a module is installed or updated. The syncer is deliberately conservative with existing data.

- New tables, nullable or defaulted columns, and indexes are applied automatically.
- **Renames are never guessed.** Declare the old attribute name on the new field:

  ```python
  margin = fields.FloatField(name='Margin', renamed_from='discount')
  ```

  The `discount` column is renamed in place and its values are preserved. Without `renamed_from`, the old column is kept as retired and the new field starts empty.
- **Removing a field keeps its column.** The field's `sys.field` row is marked `retired` instead of deleted, so the data survives until an operator drops it explicitly.
- **Type changes are applied only when the cast cannot lose data** (for example `integer → bigint`, `varchar(255) → text`). Anything that could truncate or re-parse values is reported as blocked and has to be handled deliberately. Ordinary API requests never retype a column: even a lossless change waits for an explicit module update.
- **Declared renames run on requests; drops never do.** A rename is safe when it is declared with `renamed_from`, so the app keeps working after a deploy. Type changes and drops need an operator: use the Modules page (the Update dialog shows the plan) or the CLI.

Check a pending plan without changing anything, then inspect retired columns:

```text
python -m jerp.cli --database <db> update --dry-run
python -m jerp.cli --database <db> update --allow-drop   # destructive
python -m jerp.cli --database <db> doctor                # retired columns + SQL
```

`--allow-drop` is database-wide: it drops every retired column whose model was synchronized by that update. Without it, removed fields keep their column and data.

A sync always produces a plan first; `Registry.last_schema_plan` holds the result of the last one, including the SQL and the blocked entries.

Views are React components declared with the page DSL and registered by name:

```tsx
import { Page, PageContent, Table, TableField, Form, FormField } from '@jerp/ui';

export default function Products() {
  return (
    <Page name="stock.products" title="Products" model="stock.product" searchBar create update delete>
      <PageContent>
        <Table model="stock.product">
          <TableField name="name" />
          <TableField name="price" />
        </Table>
        <Form model="stock.product" title="Product">
          <FormField name="name" />
          <FormField name="price" />
        </Form>
      </PageContent>
    </Page>
  );
}
```

## Model API

Every model exposes standard methods over a single POST endpoint; the request body is passed as keyword arguments and the response is `{"result": …}`.

```http
POST /api/model/<model>/<func>
Content-Type: application/json
```

| Method | Arguments | Purpose |
| --- | --- | --- |
| `all` | `domain`, `fields`, `order`, `limit`, `offset` | List records |
| `find` | `id`, `fields` | One record |
| `create` | field values | Create |
| `update` | `id`, `values` | Update |
| `delete` | `id` | Delete one record |
| `delete_many` | `ids` | Delete several records |
| `count` | `domain` | Count |
| `fields` | - | Field descriptors |

Custom methods are exposed with `@jerp.http.api_expose`. Instance methods receive the record selected by `id` in the body (or `draft_id`); class/static methods receive the body as keyword arguments. Fields flagged `hide=True` (for example passwords) stay in the schema and remain writable, but are never returned by reads.

### Draft API

Forms and embedded tables keep unsaved state in `temp.model` drafts, grouped by a per-form token:

| Method | Arguments | Purpose |
| --- | --- | --- |
| `new` | `token`, `values`, `reuse` | Create/reuse a row draft |
| `edit` | `id`, `token`, `values` | Draft copy of an existing record |
| `change` | `draft_id`, `values` | Apply values, run on-change + compute |
| `drafts` | `token` | Every draft in a token |
| `discard` | `draft_id` | Drop one draft |
| `discard_all` | `token` | Drop all drafts in a token |
| `remove` | `token`, `id` | Stage record deletion |
| `save` | `draft_id` | Commit the token containing one draft |
| `commit` | `token`, `parent_field`, `parent_id` | Atomic parent + child commit |

`change` returns the current `values`, `dirty` fields, `errors`, `warnings`, `domains` and `version`. The client debounces changes by 800 ms and flushes immediately on Save/commit.

## Security model

- Passwords are hashed with PBKDF2 (`pbkdf2_sha256`) before storage and excluded from API reads.
- Requests run inside a database scope chosen by the client; `/__storage/<name>` serves a file only if a matching row exists in the selected database.
- Page and menu auth is declared per entry (`auth` defaults to `true`).
- `jerp.config.json` ships placeholder development credentials — never commit real secrets or point it at production data.

## Roadmap

- Session-based authentication on top of the current cookie
- Access rights and record rules per model
- Reporting and export
- Additional modules to demonstrate the framework

## Contributing

Issues and pull requests are welcome. Keep changes consistent with the existing layout: framework code in `jerp/`, business features in `modules/<name>/`, build tooling in `tools/`. Run `npm run typecheck`, `npm run build:views` and `python -m unittest discover -s tests` before opening a pull request.

## License and attribution

Released under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution requirements.

J-ERP was created by **AbdoPrDZ** (<https://github.com/AbdoPrDZ/J-ERP>).

**If you use, redistribute or fork this project, you must keep the copyright and attribution notices — including the `NOTICE` file — and credit the original author.** Apache 2.0 requires the notices to be preserved in redistributions and derivative works; a visible credit in your README or documentation is the clearest way to comply. If you redistribute a modified version, please state that you changed it.
