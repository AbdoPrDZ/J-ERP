# Architecture

## What J-ERP Is

A small, self-contained ERP platform. It provides a declarative model/schema
framework, a module system installed per PostgreSQL database, and a React UI
assembled from a shared shell plus per-module view bundles.

## Stack

| Area | Technology |
|---|---|
| Backend | Python 3.15 (per `requirements.txt`), standard-library HTTP server |
| Database | PostgreSQL only, via `psycopg[binary]` 3 + `psycopg_pool` |
| Frontend | React 19 + TypeScript + Tailwind CSS 4, built with Vite 8 |
| Module views | esbuild bundles loaded at runtime through an import map |
| Build tooling | npm scripts in `package.json`, scripts in `tools/*.mjs` |

## Top-Level Layout

| Path | Role |
|---|---|
| `app.py` | Entry point: load config, build environment, register routes, serve |
| `jerp/` | Framework: config, DB, models, fields, schema, modules, HTTP, UI kit |
| `modules/<name>/` | Feature modules (manifest, controllers, models, views, assets) |
| `tools/` | Node build scripts and the Vite dev plugin |
| `public/` | Vite HTML entry used to produce the UI shell |
| `data/` | Runtime output (built UI, built views, uploads); gitignored — never hand-edit |
| `jerp.config.json` | Application/database configuration |

## Backend Layers

- **`jerp.config`** — loads `jerp.config.json`; `JERP_DB_*` and `JERP_APP_*`
  environment variables override connection/app settings.
- **`jerp.db`** — `Database` wraps a pooled connection; `DatabaseManager` owns one
  `Database` and one `Registry` per selected database.
- **`jerp.env`** — global `Environment` singleton holding the database manager and
  router; the active database name lives in a `ContextVar`.
- **`jerp.registry`** — per-database view of installed modules and their model
  classes.
- **`jerp.models` / `jerp.fields`** — declarative models and typed fields; a
  global `ModelRegistry` collects imported model classes. Runtime records are
  `RecordSet` lists (search/browse), many2one access returns a recordset, and
  reverse one2many attributes are discovered from child models.
- **`jerp.api`** — `api_expose`, `on_change` and `depends_on` decorators.
- **`jerp.models` drafts** — server-side draft rows in `temp.model` for forms
  and tables (`new`, `edit`, `change`, `save`, `commit`, `discard`), plus
  in-memory pseudo-records for Python `Model.new()`.
- **`jerp.schema`** — diffs declared fields against live PostgreSQL and applies
  DDL transactionally (see `database.md`).
- **`jerp.modules`** — discovers modules from `configure.json`, installs/updates/
  uninstalls them, and triggers view builds.
- **`jerp.menus`** — synchronizes declared routes into `sys.menu` on
  install/update and builds the nested menu tree for `GET /api/menu`.
- **`jerp.i18n`** — parses `.lang` catalogs, imports them into
  `sys.translation`, resolves the active user/session language and translates
  Python/API strings (`_t`).
- **`jerp.translate`** — Google Translate helpers used by the `i18n translate`
  CLI, with placeholder protection.
- **`jerp.http`** — router, request/response helpers, controller discovery,
  request-scoped database middleware.
- **`jerp.views` / `jerp.routes`** — page declarations from module manifests,
  view rendering, and page-to-route binding.
- **`jerp.uploads` / `modules/core/controller`** — file upload and storage.

Nothing connects to a database at startup. A database is selected per request
and its registry loaded on demand.

## Request Flow

1. `app.py` initializes `Environment`, imports module controllers, registers
   page routes, then starts `jerp.server`.
2. `jerp.server.Application` routes by prefix:
   - `/api/*` → router dispatch (request-scoped database)
   - `/views/<module>/*` → built module view bundles in `data/view`
   - `/__assets/<module>/*` → raw module assets in `modules/<module>/ui/assets`
   - `/__storage/<name>` → stored upload (only if registered in `files`)
   - `/__endpoints` and `/__modules` → dev-server discovery (URL prefixes and
     installed module names for the selected database)
   - static files from `data/ui`
   - registered page routes (server-rendered shell)
   - SPA fallback for HTML navigations
3. If the `jerp_db` cookie points at a missing database, HTML requests are
   redirected to `/db/manager` and the cookie is cleared.

## UI Assembly And Runtime

- The server reads `data/ui/index.html` and injects:
  - an import map at `<!--jerp:head-->`: `react*` → `/react-runtime.js`,
    `@jerp/ui` and `@jerp/locale` → `/runtime.js`
  - JSON payload scripts at `<!--jerp:body-->`: `__JERP_VIEWS__`,
    `__JERP_ROUTES__`, `__JERP_PAGES__`, `__JERP_CONTEXT__`
- Menus are not injected: the client fetches the active database's tree from
  `GET /api/menu` (backed by `sys.menu`). Search models come from
  `GET /api/models`; the UI catalog comes from `GET /api/i18n`.
- `jerp/ui/src/core/main.ts` loads the locale catalog, reads those payloads,
  registers view URLs, resolves the view from the element's `data-view`, the URL,
  or the route map, applies the login guard, and mounts the React root.
- SPA navigation (`navigation.ts`) intercepts same-origin anchors and
  `navigateTo()` calls, updates history and remounts the view inside the shell.
  `loading.ts` drives the top progress bar/spinner; the drawer and view
  transitions are CSS-animated.
- The Home dashboard shows live model counts. Quick-access links and the
  `add_to_home` route option are currently removed.
- `runtime.js` is built from `jerp/ui/src/core/runtime.ts` and re-exports the
  shared UI kit. `react-runtime.js` is generated from React's runtime keys so the
  shell and every module share one React instance.
- Module views are compiled per module by `tools/build-views.mjs` into
  `data/view/<module>/` with `manifest.json`; view key is
  `<module>.<snake_case_file>`.
- In development, Vite serves the shell. `tools/vite-plugin-jerp.mjs` asks the
  backend for its URL prefixes via `GET /__endpoints`, then for each HTML request
  fetches `GET /__modules` with the browser's `jerp_db` cookie to inject only the
  installed modules' views, routes and page metadata. With no database or an
  unreachable backend it exposes `core` only.

## Model Runtime

- `search()` and `browse()` return `RecordSet` (a `list` subclass) supporting
  `is_one()`/`ensure_one()` and attribute proxying for a single record.
- A many2one field reads as a `RecordSet` of the related record, so
  `line.product_id.name` works; `read()` still returns raw ids for the API/UI.
- Reverse one2many attributes (`order.lines`) are discovered from child many2one
  fields. Assigning `(0, 0, values)`, `(1, id, values)`, `(2, id)` or
  `(6, 0, ids)` commands creates/updates/removes children.
- `compute='_method'` fields evaluate lazily on access; `@depends_on([...])`
  records dependencies. Stored values are recomputed on create/write/commit/save.
- `@on_change([...])` handlers run server-side on a pseudo-record; assignments are
  diffed into changed values and dependent computes follow. Both instance-style
  (`self` mutations) and classmethod/value-dictionary handlers are supported.
- `Model.new()` without a token returns an in-memory pseudo-record; `record.save()`
  writes it (and its one2many children) in one transaction. With a token it
  creates a server-side draft used by forms.

## Module System

- A module is a directory under `modules/` containing `configure.json`
  (`name`, `version`, `summary`, `depends`, optional `logo`, `routes`).
- `core` is the base module: always installed first, cannot be uninstalled, and
  owns system models (`sys.module`, `sys.model`, `sys.field`, `sys.menu`,
  `sys.translation`, `sys.lang`, `sys.contact`, `sys.user`, `sys.file`,
  `temp.model`).
- Installation is **per database**: it synchronizes the module's models and
  records the module in that database's `sys_module`.
- Modules may provide `controller/` (auto-discovered routes), `models/`, and
  `ui/src/views/` (compiled view bundles).
- Backend imports use the package path `modules.<name>...`; the modules folder
  name is the package name.

## Boundaries

- Framework behavior belongs in `jerp/`; business features belong in `modules/`.
- `data/` is build/runtime output. Regenerate it with npm scripts, never edit it.
- Frontend modules import the shared kit from `@jerp/ui`, not by relative path
  into `jerp/ui`.
