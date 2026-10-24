# Context Structure Specification

Defines the context layout and the responsibility of each file. This file
changes only when the organization of the context changes — not for content
updates.

## Core Files (always present)

| File | Responsibility | Does not contain |
|---|---|---|
| `README.md` | Entry point: what the context is, reading order, navigation by task | Project details duplicated from other files |
| `config.md` | Maintenance configuration (update mode, detail, scope, template) | Project knowledge |
| `structure.md` | This contract: file set, responsibilities, detail levels, creation rules | Project knowledge |

## Project Files

| File | Responsibility | Does not contain |
|---|---|---|
| `architecture.md` | Purpose, stack, layers, process/request flow, module system, build pipeline, top-level layout | Per-class or per-endpoint detail |
| `database.md` | PostgreSQL-only model, per-database registry, declarative schema sync (plan/apply, rename/retire rules), system tables, data-safety constraints | Full table/column inventories |
| `api.md` | HTTP surface: model API contract, conventions for responses/errors, database scoping, uploads/storage, auth behavior | Handler-by-handler listings |
| `workflows.md` | Recurring procedures: run, build, install module, add model/field, add page/view | Unstable temporary notes |
| `conventions.md` | Code style, naming, module boundaries, frontend conventions, safety and verification rules | Generic language tutorials |

## Domains

`domains/README.md` indexes the domain files. A domain file covers purpose,
important entities, business rules, relationships, workflows, integrations and
project-specific constraints.

| File | Exists when |
|---|---|
| `domains/framework.md` | Always — the custom `jerp/` framework is the core of the system |
| `domains/auth.md` | Authentication/session behavior exists (it does) |
| `domains/ui.md` | The shared React UI kit and module view pipeline exist (they do) |
| `domains/stock.md` | A stock/business module exists (it does) |
| `domains/sale.md` | Sales orders and lines exist (they do) |

Create a new domain file only for a **meaningful domain**, never one per module,
model or table. Promote it only through a deliberate structure change.

## Detail Levels

- **minimal**: `README.md`, `config.md`, `structure.md`, `architecture.md`.
- **standard** (current): above + `database.md`, `api.md`, `workflows.md`,
  `conventions.md`, `domains/`.
- **detailed**: standard + `decisions.md`, `infrastructure.md`,
  `integrations.md`, plus deeper domain files. None of these exist yet.

Files outside the current level must not exist. Files inside it must stay within
their declared responsibility.

## Maintenance Rules

- Update only the smallest set of affected files; never rewrite the whole
  context for a local change.
- Keep domain knowledge out of `architecture.md` when it belongs in a domain file.
- Remove stale statements rather than layering contradictions.
- Do not add inventories of files, classes, functions, endpoints or columns.
