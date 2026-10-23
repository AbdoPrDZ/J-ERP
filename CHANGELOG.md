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

#### UI

- Draft-aware `Form`, `FormTable` and `Many2oneField`; inline row editing,
  multiple draft rows via `reuse: false`, 800 ms debounced changes and live
  parent totals.
- Sticky navbar/page/table headers, server-side table pagination/sorting, card
  pagination, field validation and label fallbacks.
- Modern Home dashboard with live counts and menu-driven quick access via
  `add_to_home`.
- Redesigned login (full logo, split brand/form layout, password visibility) and
  database manager (card layout, stats, refreshed modals, no shell navbar).
- New full logo asset and favicon.

#### Navigation and tooling

- `add_to_home` and `description` route options; server-injected
  `__JERP_HOME__` built from installed modules (groups and hidden pages allowed).
- Vite dev payload is filtered by installed modules through the new
  `GET /__modules` endpoint instead of exposing every module on disk.
- `build:views` now validates that every declared menu view has a build file and
  supports nested view folders (`views/pages/*`).
- Unit test suite (`tests/`) with ORM/API compatibility tests.

#### Modules

- `sale` module with orders/lines, computed subtotal/total, product on-change,
  read-only cost, state actions (`confirm`, `done`, `cancel`, `reset_to_draft`)
  and an order form with an inline line table.
- `core` technical pages for Models, Fields, Menus and Data; organization pages
  moved under `views/pages/`.
- `stock` product cost and selling price fields.

### Changed

- Schema sync backfills new required columns on non-empty tables with neutral
  values and drops incompatible defaults before type changes.
- `temp.model.dirty` migrated to JSONB; draft reads accept dicts and legacy JSON
  strings.
- Menus and home shortcuts are resolved from the database's `sys_module` on each
  render, so external installs/uninstalls appear after a refresh.
- Seed/multilingual writes no longer re-enter `ensure_loaded` recursively.

### Fixed

- Login hanging during localization seeds (recursive seed application).
- Login `server_error` when `temp.model.dirty` changed from text to JSONB.
- Sales/Stock menus lingering after uninstall in production and Vite dev.
- Duplicate inline draft row in embedded tables.

### Planned

- Session-based authentication on top of the current user cookie
- Access rights and record rules per model
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
