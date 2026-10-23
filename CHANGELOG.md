# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
