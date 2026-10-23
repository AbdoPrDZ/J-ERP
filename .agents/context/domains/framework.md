# Domain: Framework (`jerp/`)

## Purpose

`jerp/` is the platform layer: configuration, database access, declarative
models, schema synchronization, module lifecycle, HTTP routing, view rendering,
uploads and the shared UI kit. Business behavior belongs in `modules/`.

## Important Concepts

### Environment and database selection

- `Environment` is a singleton created once (`Environment.init_instance`).
- It holds `DatabaseManager` and the HTTP `Router`.
- The active database name is a `ContextVar`; `environment.using(name)` scopes a
  block to a database. Every dispatched request enters that scope based on the
  `jerp_db` cookie / `X-JERP-DB` header.
- `environment.db` is the active `Database`; `environment.registry()` is the
  active per-database `Registry`.

### Models and fields

- `ModelMeta` collects `Field` descriptors, builds `_fields`, derives `_name`
  and `_table` from the class name, and registers concrete models globally.
- Fields are descriptors: `record.name` reads the stored value; `Model.name`
  returns the field metadata.
- `Model` provides raw CRUD (`create`, `search`, `browse`, `write`, `unlink`)
  and API-facing helpers (`all`, `count`, `find`, `update`, `delete`, `fields`)
  marked with `@api_expose`.
- Standard columns come from `BaseModel`: `id`, `created_at`, `updated_at`.
- `_views` may restrict fields per standard view type; `_label` chooses the
  display label; `_virtual` excludes a model from schema syncing.

### Registry and module lifecycle

- `Registry` is the runtime view of one database: installed modules and the
  model classes they contribute.
- `ModuleManager.discover()` reads `modules/*/configure.json` and imports the
  module packages so metaclasses register their models.
- `install` resolves dependency order (`core` first), syncs the schema, records
  `sys_module`, and builds views.
- Model classes are global (import-time), but the per-database registry filters
  them by installed modules. This is what makes per-database module sets work.

### HTTP

- `Router` supports literal and `<param>` endpoints; `dispatch` applies the
  database scope and request binding, then calls the handler.
- `@route`/`@get`/`@post` record metadata on the function and register it on the
  environment router. `load_controllers` then re-registers class methods as
  bound handlers so `self` works.
- `Request` exposes cookies, query, headers, body and JSON; `response` helpers
  build JSON, redirects, rendered pages and errors.

### Views and pages

- Pages are declared in module manifests, not code. `jerp.views` collects pages,
  menus and the view map; `jerp.routes` binds page endpoints to a handler that
  enforces the login guard and renders the SPA shell.
- `ViewRenderer` injects the import map and JSON payloads into the built shell.
  `<!--jerp:head-->` and `<!--jerp:body-->` markers in `public/index.html` are
  required for this to work.

### Uploads

- `jerp.uploads` stores to `data/uploads/tmp`, then moves to
  `data/uploads/files` on confirm. Stored names are generated tokens; metadata
  lives in the `file` model. `/__storage/<name>` refuses unregistered files.

## Constraints

- Do not add framework logic to modules or module logic to `jerp/`.
- Preserve per-database isolation: never assume one global module set.
- Keep `core` installable before any other module.
- Schema sync is destructive-capable; changes to syncer logic can drop data.
- Route decorators execute at import time, so controllers must be import-safe
  without an active database (lazy-import database-touching models).
