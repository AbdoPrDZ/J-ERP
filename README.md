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
- **Module-declared navigation** - menus, routes, page options, auth requirements and `add_to_home` shortcuts live in each module's `configure.json`.
- **Declarative page DSL** - compose pages from `Page`, `Table`, `Cards`, `Form`, `FormTable`, `FormField`, `FormGroup`, `Action` and friends; no per-view plumbing.
- **Typed model API** — a single endpoint (`POST /api/model/<model>/<func>`) plus a typed client, instead of hand-written controllers for every screen.
- **Views built on install** — module view bundles are compiled with esbuild into `data/view/<module>/` and loaded through an import map.
- **Files and images** — two-step uploads, a `File` model, `FileField`/`ImageField` widgets, and storage served only for files known to the active database.
- **Auth included** — users with hashed passwords (PBKDF2), hidden fields that never leave the server, and login/profile pages.

## Architecture

```
app.py                  HTTP entrypoint (host/port from jerp.config.json)
jerp/                   Framework: ORM, schema sync, router, server, views, modules
  models.py             Model metaclass, recordsets, CRUD, computed fields, drafts
  fields.py             Field types (char, text, int, float, date, file, image, password, …)
  api.py                Decorators: api_expose, on_change, depends_on
  schema.py             Declarative schema synchronization
  modules.py            Module discovery, install/update/uninstall, build hooks
  views.py              Menu/route/view collection and shell rendering
  server.py             HTTP dispatch, static + asset + storage routes
  ui/                   Shared React runtime, page DSL and field widgets
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
```

## Configuration

`jerp.config.json`:

| Key | Meaning |
| --- | --- |
| `databases.host` / `port` / `user` / `password` / `sslmode` | PostgreSQL connection settings |
| `databases.owner` | Only databases owned by this role are listed (defaults to the connecting user) |
| `app.host` / `app.port` | HTTP bind address (default `127.0.0.1:1347`) |
| `database` | Optional default database for standalone `Environment()` / `JERP_DATABASE` |
| `modules_path` | Where modules are discovered (`modules`) |
| `schema` | PostgreSQL schema used for tables (`public`) |
| `ui_dist` | Built UI directory (`data/ui`) |
| `views_dir` | Built module view bundles (`data/view`) |
| `uploads_dir` | Uploaded files (`data/uploads`) |

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

Route entries accept `label`, `view`, `endpoint`, `params`, `sequence`, `img`, `description`, `auth`, `header`, `menu`, `drawer`, `hide`, `add_to_home` and nested `children`. `sequence` orders the navigation tree; `auth` defaults to `true`; `add_to_home: true` adds a quick-access card (groups link to their first page, and hidden pages are allowed).

Models are plain Python classes:

```python
from jerp import fields, models


class Product(models.Model):
  _name = 'stock.product'

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
