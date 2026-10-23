# J-ERP

**A modular, self-hosted ERP framework where modules own everything — models, schema, menus, pages and views.**

J-ERP pairs a small declarative Python ORM over PostgreSQL with a React 19 + TypeScript + Tailwind SPA. Modules are installed **per database**: installing or updating a module synchronizes its schema in a single transaction, so there are no migration files to write or maintain. Each module also ships the menus, routes and views it contributes, which the server injects into the shell and the client loads dynamically.

[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.15-3776AB.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/react-19-61DAFB.svg)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/postgresql-%3E%3D14-4169E1.svg)](https://www.postgresql.org/)

---

## Highlights

- **Per-database modules** — one server, many independent databases, each with its own set of installed modules and its own schema.
- **No migrations** — models are declared in Python; the schema is diffed and synchronized transactionally on install/update.
- **Multi-database management** — create, list, select and drop databases from the UI; access is scoped to the configured owner.
- **Module-declared navigation** — menus, routes, page options and auth requirements live in each module's `configure.json`.
- **Declarative page DSL** — compose pages from `Page`, `Table`, `Cards`, `Form`, `FormField`, `FormGroup`, `Action` and friends; no per-view plumbing.
- **Typed model API** — a single endpoint (`POST /api/model/<model>/<func>`) plus a typed client, instead of hand-written controllers for every screen.
- **Views built on install** — module view bundles are compiled with esbuild into `data/view/<module>/` and loaded through an import map.
- **Files and images** — two-step uploads, a `File` model, `FileField`/`ImageField` widgets, and storage served only for files known to the active database.
- **Auth included** — users with hashed passwords (PBKDF2), hidden fields that never leave the server, and login/profile pages.

## Architecture

```
app.py                  HTTP entrypoint (host/port from jerp.config.json)
jerp/                   Framework: ORM, schema sync, router, server, views, modules
  models.py             Model metaclass, fields, CRUD, standard model API
  fields.py             Field types (char, text, int, float, date, file, image, password, …)
  schema.py             Declarative schema synchronization
  modules.py            Module discovery, install/update/uninstall, build hooks
  views.py              Menu/route/view collection and shell rendering
  server.py             HTTP dispatch, static + asset + storage routes
  ui/                   Shared React runtime, page DSL and field widgets
modules/<name>/         Feature modules (models, controllers, views, assets)
  configure.json        Module metadata, menus/routes, dependencies
tools/                  Vite plugin and build scripts
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

The Vite dev server discovers API/asset/storage proxies at startup by calling the backend's `GET /__endpoints`. If the backend was down when Vite started, restart Vite.

### Useful commands

```bash
python app.py --port 9000            # override the port
python app.py --host 0.0.0.0         # expose on the network
npm run typecheck                    # tsc -b
npm run build                        # UI shell + shared runtime -> data/ui
npm run build:views                  # module view bundles -> data/view
npm run build:all                    # both
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

Route entries accept `label`, `view`, `endpoint`, `params`, `sequence`, `auth`, `header`, `menu`, `hide` and nested `children`. `sequence` orders the navigation tree; `auth` defaults to `true`.

Models are plain Python classes:

```python
from jerp import fields, models


class Product(models.Model):
  _table = 'products'

  name = fields.StringField(name='Name', required=True)
  price = fields.FloatField(name='Price')
  image = fields.ImageField(name='Image')
```

Views are React components declared with the page DSL and registered by name:

```tsx
import { Page, PageContent, Table, TableField, Form, FormField } from '@jerp/ui';

export default function Products() {
  return (
    <Page name="stock.products" title="Products" model="product" searchBar create update delete>
      <PageContent>
        <Table model="product">
          <TableField name="name" label="Name" />
          <TableField name="price" label="Price" />
        </Table>
        <Form model="product" title="Product">
          <FormField name="name" label="Name" />
          <FormField name="price" label="Price" />
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
| `delete` | `ids` | Delete |
| `count` | `domain` | Count |
| `fields` | — | Field descriptors |

Custom methods are exposed with `@jerp.http.api_expose`. Fields flagged `hide=True` (for example passwords) stay in the schema and remain writable, but are never returned by reads.

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

Issues and pull requests are welcome. Keep changes consistent with the existing layout: framework code in `jerp/`, business features in `modules/<name>/`, build tooling in `tools/`. Run `npm run typecheck` before opening a pull request.

## License and attribution

Released under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution requirements.

J-ERP was created by **AbdoPrDZ** (<https://github.com/AbdoPrDZ/J-ERP>).

**If you use, redistribute or fork this project, you must keep the copyright and attribution notices — including the `NOTICE` file — and credit the original author.** Apache 2.0 requires the notices to be preserved in redistributions and derivative works; a visible credit in your README or documentation is the clearest way to comply. If you redistribute a modified version, please state that you changed it.
