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
- `Environment()` with no arguments is a standalone convenience: it loads
  `jerp.config.json`, chooses `JERP_DATABASE`/the configured database/`J-ERP`/the
  only database, and supports `env['model']` mapping access.
- Installed module names still come from `sys_module`; menus come from `sys.menu`
  (synced on install/update) and translations from `sys.translation`.

### Models and fields

- `ModelMeta` collects `Field` descriptors, builds `_fields`, derives `_name`
  and `_table` from the class name, and registers concrete models globally.
- Fields are descriptors: `record.name` reads the stored value; `Model.name`
  returns the field metadata. Field constructors accept the Odoo-style positional
  form for relations/selections: `Many2oneField('sys.contact', name='Customer')`
  and `SelectionField(STATE_SELECTION, name='Status')`.
- `Model` provides raw CRUD (`create`, `search`, `browse`, `write`, `unlink`)
  and API-facing helpers (`all`, `count`, `find`, `update`, `delete`,
  `delete_many`, `fields`) marked with `@api_expose`.
- Standard columns come from `BaseModel`: `id`, `created_at`, `updated_at`.
- `_views` may restrict fields per standard view type; `_label` chooses the
  display label; `_virtual` excludes a model from schema syncing.
- `search`/`browse` return `RecordSet`; many2one access returns a recordset of
  the related record, while `read()` returns raw ids. Reverse one2many attributes
  are derived from child many2one fields (`sale.order.lines` ←
  `sale.order.line.order_id`).
- Computed fields use `compute='_method'`; `@depends_on([...])` declares
  dependencies. Values evaluate lazily and are recomputed/persisted on
  create/write/draft commit/`save`.
- `@on_change([...])` runs server-side on a pseudo-record. Instance handlers
  mutate `self` (`for record in self`); assignments are diffed into changed
  values. Legacy classmethod handlers returning a dict still work.
- `Model.new()` (no token) creates an in-memory pseudo-record; `record.save()`
  writes it and one2many children atomically. `new(token=...)` creates server
  drafts for forms. `Model.save(draft_id)` remains the class/API form via a
  dual-dispatch descriptor.
- `create` accepts a positional values dict in Python and keyword values over
  HTTP; missing required text values are stored as `''`, and numeric new-record
  defaults are `0`.

### Draft records

- `temp.model` stores server-side drafts for forms/tables. `jerp.models`
  implements `new`, `edit`, `change`, `drafts`, `discard`, `discard_all`,
  `remove`, `save` and `commit`.
- Draft `data` is a JSON text snapshot; `dirty` is JSONB. `change` runs on-change
  and compute, persists the new values, and refreshes computed values on parent
  drafts. `commit` writes the whole token in a single transaction, resolving
  `draft:<id>` relations and checking `base_stamp`.
- Parent forms and `FormTable` rows share a token; child rows use
  `reuse: false` (`new` with `reuse: false`) so multiple rows can be added.

### Registry and module lifecycle

- `Registry` is the runtime view of one database: installed modules and the
  model classes they contribute.
- `ModuleManager.discover()` reads `modules/*/configure.json` and imports the
  module packages so metaclasses register their models.
- `install` resolves dependency order (`core` first), syncs the schema, records
  `sys_module`, builds views, synchronizes `sys.menu`, and imports `.lang` files
  for active languages into `sys.translation`.
- `update` re-syncs menus and active-language translations; `uninstall` removes
  the module's menu/translation rows and drops its tables.
- `Registry.preview()` plans a whole-database sync without applying it;
  `retired_fields()` lists retired columns. Request-path sync (`sync_dirty`)
  applies safe changes and declared renames but defers type changes and drops;
  `install`/`update` call `init_models()` and raise `SchemaBlocked` after
  committing the safe part.
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

### Views, menus and pages

- Pages are declared in module manifests, not code. `jerp.views` collects pages,
  the view map and page metadata; `jerp.routes` binds page endpoints to a handler
  that enforces the login guard and renders the SPA shell.
- `jerp.menus` turns labelled, non-hidden route entries into `sys.menu` rows on
  install/update, removes them on uninstall, and builds the nested tree read by
  `GET /api/menu`. `add_to_home` and Home quick-access links are currently
  removed.
- `ViewRenderer` injects the import map and JSON payloads into the built shell
  (`__JERP_VIEWS__`, `__JERP_ROUTES__`, `__JERP_PAGES__`, `__JERP_CONTEXT__`).
  `@jerp/ui` and `@jerp/locale` both resolve to `/runtime.js`.
  `<!--jerp:head-->` and `<!--jerp:body-->` markers in `public/index.html` are
  required for this.
- In dev, `tools/vite-plugin-jerp.mjs` builds the views/routes/pages payload from
  disk but filters modules using `GET /__modules` and the `jerp_db` cookie.

### Translation

- `jerp.i18n` parses flat `.lang` files, imports active languages into
  `sys.translation`, resolves user/cookie/default language, and exposes
  `translate()` / `_t()` for Python messages.
- `Model.field_schema()` and `view_descriptor()` translate labels, help,
  selections, titles and descriptions from `model.<model>.*` keys. Menus and
  module summaries are translated at read time.
- `Language.write(active=True)` reloads that language's files for every installed
  module. New databases seed English as the only active language.
- `jerp.translate` contains the optional Google Translate client used by the CLI;
  placeholders such as `{name}` are protected/restored.

### Deletion protection

- `Record.unlink()` checks every installed model for a many2one or file/image
  field pointing at the record and raises a translated `ValueError` when found;
  `delete_many()` wraps the batch in one transaction.

### Uploads

- `jerp.uploads` stores to `data/uploads/tmp`, then moves to
  `data/uploads/files` on confirm. Stored names are generated tokens; metadata
  lives in the `file` model. `/__storage/<name>` refuses unregistered files.

## Constraints

- Do not add framework logic to modules or module logic to `jerp/`.
- Preserve per-database isolation: never assume one global module set.
- Keep `core` installable before any other module.
- Schema sync is conservative but not read-only: it adds tables/columns/indexes
  automatically, renames only via `renamed_from`, retires removed columns, and
  refuses lossy type changes. Ordinary requests apply safe changes but defer
  type changes; only explicit install/update retype. `allow_drop=True` (and
  module uninstall) can destroy data - preview with `preview`/`--dry-run`/
  `doctor` and treat syncer changes accordingly.
- Route decorators execute at import time, so controllers must be import-safe
  without an active database (lazy-import database-touching models).
