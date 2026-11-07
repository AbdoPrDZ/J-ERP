# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### ORM and drafts

- Odoo-style model compatibility: positional `Many2oneField`/`SelectionField`
  constructors, `compute=` fields, `@depends_on`, instance-style `@on_change`,
  recordsets with `is_one()`/`ensure_one()`, many2one record access and
  auto-discovered one2many relations with `(0/1/2/6, …)` commands.
- In-memory `Model.new()` / `record.save()` for Python callers, `create(dict)`,
  `Environment()` standalone convenience, `env['model']` mapping access and
  `from jerp import Environment`.
- Server-side form/table drafts in `temp.model`: `new`, `edit`, `change`,
  `drafts`, `discard`, `discard_all`, `remove`, `save` and transactional
  `commit`; `draft:<id>` relation refs, `base_stamp` conflict checks and parent
  computed-value refresh.
- Instance `@api_expose` dispatch (body `id`/`draft_id`) and the dual
  `Model.save(draft_id)` / `record.save()` method.
- Computed fields are evaluated on read and persisted on create/write/commit;
  parent totals are recomputed after child rows commit.
- Deletes are refused when another record still references the target through a
  many2one or file/image field (for example a country used by states); bulk
  deletes run in one transaction so a blocked row leaves nothing half-deleted.

#### Schema sync and migrations

- Schema plans: every install/update can be previewed without changing the
  database (`module.preview`, `update --dry-run`), with the exact SQL, warnings
  and blocked entries.
- Renames are no longer guessed: a column moves only when the field declares
  `renamed_from`; otherwise the old column is kept and the new field starts
  empty.
- Removed fields are retired instead of dropped: their `sys.field` row is marked
  `retired`, the column stays, and `doctor` lists it with the SQL that would
  drop it. `update --allow-drop` (or the dialog toggle) drops retired columns
  database-wide.
- Type changes apply only when the dialect can cast them without loss; the
  request path defers even lossless changes, and ordinary requests never drop or
  retype a column.
- Versioned data migrations: `modules/<module>/migrations/<version>/pre-*.py`
  and `post-*.py` scripts define `migrate(cr, version)` and run inside the
  lifecycle transaction, `pre` against the old schema and `post` against the
  new one. Folders run only when the module version moves forward; fresh
  installs and `update(force=True)` never re-run them.
- Module lifecycle is atomic: dependency ordering, schema sync, migrations and
  `sys_module` version rows commit together, so a failed script or blocked
  change rolls the whole update back with the version unchanged. Menus and
  translations are refreshed after the commit because they depend on the
  language seed data.
- `uninstall` runs in one transaction over table drops, extension-column
  synchronization, the `sys_module` row and menu/i18n cleanup.
- Module dependency cycles (`A → A`, `A → B → A`) are detected and reported
  with the cycle path during discovery and registry loading.

#### Security

- Server-side login sessions: `sys.session` stores a SHA-256 digest of a random
  token, sent as an `HttpOnly`, `SameSite=Lax` cookie (`Secure` behind HTTPS).
  Logout revokes the row and expired sessions are pruned. The old
  `jerp_user=<username>` cookie is no longer read or written.
- Router-level authentication is deny-by-default: every route requires a
  session unless it declares `auth=False` (login/logout, language catalog,
  database manager). API calls get `401`, page requests redirect to `/login`.
- `sys.user.is_admin` and role checks: module install/update/uninstall/preview
  and the `sys.module`/`sys.model`/`sys.field`/`sys.session`/`sys.translation`
  APIs require an administrator. Non-admins can only read and edit their own
  account, cannot change `is_admin`, and cannot list other users. Existing
  accounts are promoted when the column is added; the first account of a new
  database is created as an administrator.
- Login throttling (five failures per account per five minutes -> `429`).
- Request bodies over 20 MB are rejected with `413`, and idle connections time
  out after 60 seconds.

#### UI

- Draft-aware `Form`, `FormTable` and `Many2oneField`; inline row editing,
  multiple draft rows via `reuse: false`, 800 ms debounced changes and live
  parent totals.
- Sticky navbar/page/table headers, server-side table pagination/sorting, card
  pagination, field validation and label fallbacks.
- SPA navigation for menu and internal links: clicks update the URL with the
  History API and mount the next view inside the existing shell instead of
  reloading the whole page.
- Shell motion: a delayed global loading bar/spinner for API calls and view
  mounts, animated drawer open/close with staggered links, view fade-ins and
  animated header dropdowns.
- The command palette loads searchable models from `GET /api/models` with
  `Cache-Control: no-store` on every open instead of using injected page data.
- Modern Home dashboard with live counts.
- The core Menus page is a normal editable table/form over `sys.menu` (create,
  update, delete) instead of a read-only tree; manual edits stay local and are
  replaced when the owning module is updated.
- Redesigned login (full logo, split brand/form layout, password visibility) and
  database manager (card layout, stats, refreshed modals, no shell navbar).
- New full logo asset and favicon.

#### Navigation and tooling

- Database-backed navigation: a new `sys.menu` model is synchronized from each
  installed module's `configure.json` on install/update, and `GET /api/menu`
  returns the active database's nested menu tree.
- Vite dev payload is filtered by installed modules through the new
  `GET /__modules` endpoint instead of exposing every module on disk.
- `build:views` now validates that every declared menu view has a build file and
  supports nested view folders (`views/pages/*`).
- Unit test suite (`tests/`) with ORM/API compatibility tests.

#### Internationalization

- Flat `modules/<module>/i18n/<lang>.lang` catalogs (`key = value`) with a
  scaffold/check/import CLI, plus the `sys.translation` runtime table imported
  only on module install/update (files win).
- Server-side translation of field labels/help/selection labels, model titles,
  model descriptions, menu labels/descriptions and module summaries.
- `@jerp/locale` with `t()`, `GET /api/i18n`, `POST /api/lang`, RTL direction and
  a user-menu language selector; the shell, dashboard, shared table/form/card/
  pagination components, command palette, login and core module pages use
  translation keys without inline fallback text (the database manager stays
  English-only).
- Python messages use `_t('key', 'English source', **params)`; the scaffold
  collects model/field/description/menu keys, Python `_t()` calls and UI `t()`
  calls from `.ts`/`.tsx` files.
- Per-user language preference via `sys.user.lang_id`, with `jerp_lang` as the
  anonymous/session fallback.
- New databases start with English as the only active language. Activating a
  language through `sys.lang` loads that language's `.lang` files for every
  installed module; module installs/updates only import active languages.
- Database deletion now terminates the application's own sessions and, when
  optional `databases.admin_user` credentials are configured, force-drops the
  database even when pgAdmin or another superuser session is connected.
- `i18n translate` CLI command: fills blank `.lang` values through Google
  Translate for one module/language pair per run (Cloud API key or public
  endpoint), with placeholder protection, dry-run, overwrite and configurable
  request delay. `i18n import` also accepts a language filter.

#### Modules

- `sale` module with orders/lines, computed subtotal/total, product on-change,
  read-only cost, state actions (`confirm`, `done`, `cancel`, `reset_to_draft`)
  and an order form with an inline line table.
- `core` technical pages for Models, Fields, Menus and Data; organization pages
  moved under `views/pages/`.
- `stock` product cost and selling price fields.

### Changed

- Authentication is now server-side: the `jerp_user` username cookie is gone, so
  everyone signs in again after upgrading. `jerp_session` is HttpOnly, which
  means the client reads the signed-in user from `__JERP_CONTEXT__` instead of
  `document.cookie`.
- Module lifecycle operations and technical system-model APIs require an
  administrator; user management is limited to admins except for self-service
  profile edits.
- `sys.user` gains `is_admin` (required, default `true` so existing accounts stay
  privileged); user creation through the API defaults it to `false`.
- Schema sync backfills new required columns on non-empty tables with neutral
  values and drops incompatible defaults before type changes.
- `temp.model.dirty` migrated to JSONB; draft reads accept dicts and legacy JSON
  strings.
- Menus are loaded from `sys.menu` through `GET /api/menu`; the
  `__JERP_MENUS__` and `__JERP_HOME__` shell payloads were removed.
- Home quick access and the `add_to_home` option were removed for now; the
  option is kept in manifests but ignored until the home layout is redesigned.
- Seed/multilingual writes no longer re-enter `ensure_loaded` recursively.
- A blocked module update now reports that nothing was applied: the safe part of
  the plan is rolled back with the blocked part instead of being committed
  first.
- The database manager page remains English-only because it renders before any
  database/language catalog is available.
- Database drops use the optional admin role for a forced `DROP DATABASE ...
  WITH (FORCE)`; otherwise the error lists blocking pgAdmin/other sessions.

### Fixed

- The Vite dev shell injected an empty `__JERP_CONTEXT__`, so the client-side
  login guard sent signed-in users back to `/login`; the dev plugin now reads
  the session from `GET /__session` (using the browser's cookies).
- Login hanging during localization seeds (recursive seed application).
- Login `server_error` when `temp.model.dirty` changed from text to JSONB.
- Sales/Stock menus lingering after uninstall in production and Vite dev.
- Duplicate inline draft row in embedded tables.

### Planned

- Access rights and record rules per model (groups, per-model ACLs)
- Upload type whitelisting and per-user quotas
- Reporting and data export

## [1.0.0] - 2026-10-23

First public release.

### Added

#### Framework

- Declarative ORM: models, field descriptors, per-database model registry, CRUD and search.
- Field types including string, text, integer, float, boolean, date/datetime, selection, many2one, file, image and password.
- Transactional schema synchronization on module install/update — no migration files.
- Virtual models (no table), model labels (`_label` / `display_name`) and hidden fields excluded from API reads.
- Standard model API (`all`, `find`, `create`, `update`, `delete`, `count`, `fields`) plus `@api_expose` for custom methods, served at `POST /api/model/<model>/<func>`.
- Multi-database manager: create, list, select and drop databases, owner-scoped listing, automatic admin seeding and single-database auto-selection.
- Module manager: discovery, dependency-driven install, update and uninstall, with schema sync and per-module view builds.
- HTTP layer: path-parameter routing, controller discovery from modules, SPA fallback, static UI, `/__assets` and `/__storage` routes, and `/__endpoints` discovery for the dev server.
- Configuration-driven page routes with optional endpoints, auth guards and redirects.

#### UI

- React 19 + TypeScript + Tailwind CSS 4 shell with a built runtime in `data/ui` and per-module view bundles in `data/view`.
- Declarative page DSL: `Page`, `PageHeader`, `PageContent`, `Breadcrumb`, `Table`, `TableField`, `Cards`, `Form`, `FormField`, `FormGroup`.
- `Action` modal components (`Action`, `ActionHeader`, `ActionContent`, `ActionFooter`) with a ⋯ action menu on forms.
- Field widget registry, view registry and utility registry, with dynamic route/view resolution on the client.
- Navigation drawer for root menus, header sub-navigation and per-entry `sequence` ordering.
- User avatar menu with profile page and logout.
- Vite plugin that injects menus, routes and pages in development and collects API proxies from the backend.

#### Core module

- Database manager page for creating, selecting and dropping databases.
- Users model with login by `username`, display `name`, avatar image and PBKDF2 password hashing.
- Change Password action on the user form; profile page for the current user.
- Modules page backed by the virtual `Module` model.
- Two-step upload flow (`data/uploads/tmp` → confirm → `data/uploads/files`) with a `File` model.

#### Stock module

- Products model with name and image.
- Products list/cards/form page with row and card click-to-open.

### Notes

- PostgreSQL is the only supported database.
- No database is created at startup; create one from the UI or the CLI.
- `data/` (built UI, view bundles, uploads) and `node_modules/` are generated and not tracked.
