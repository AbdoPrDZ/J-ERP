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
  global `ModelRegistry` collects imported model classes.
- **`jerp.schema`** — diffs declared fields against live PostgreSQL and applies
  DDL transactionally (see `database.md`).
- **`jerp.modules`** — discovers modules from `configure.json`, installs/updates/
  uninstalls them, and triggers view builds.
- **`jerp.http`** — router, request/response helpers, controller discovery,
  request-scoped database middleware.
- **`jerp.views` / `jerp.routes`** — page declarations from module manifests,
  menus, view rendering, and page-to-route binding.
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
   - static files from `data/ui`
   - registered page routes (server-rendered shell)
   - SPA fallback for HTML navigations
3. If the `jerp_db` cookie points at a missing database, HTML requests are
   redirected to `/db/manager` and the cookie is cleared.

## UI Assembly And Runtime

- The server reads `data/ui/index.html` and injects:
  - an import map at `<!--jerp:head-->`: `react*` → `/react-runtime.js`,
    `@jerp/ui` → `/runtime.js`
  - JSON payload scripts at `<!--jerp:body-->`: `__JERP_VIEWS__`,
    `__JERP_ROUTES__`, `__JERP_PAGES__`, `__JERP_MENUS__`, `__JERP_CONTEXT__`
- `jerp/ui/src/core/main.ts` reads those payloads, registers view URLs, resolves
  the view from the element's `data-view`, the URL, or the route map, applies the
  login guard, and mounts the React root.
- `runtime.js` is built from `jerp/ui/src/core/runtime.ts` and re-exports the
  shared UI kit. `react-runtime.js` is generated from React's runtime keys so the
  shell and every module share one React instance.
- Module views are compiled per module by `tools/build-views.mjs` into
  `data/view/<module>/` with `manifest.json`; view key is
  `<module>.<snake_case_file>`.
- In development, Vite serves the shell; `tools/vite-plugin-jerp.mjs` asks the
  backend for its URL prefixes via `GET /__endpoints` and proxies them.

## Module System

- A module is a directory under `modules/` containing `configure.json`
  (`name`, `version`, `summary`, `depends`, optional `logo`, `routes`).
- `core` is the base module: always installed first, cannot be uninstalled, and
  owns system models (`sys.module`, `sys.model`, `sys.field`, `users`, `files`).
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
