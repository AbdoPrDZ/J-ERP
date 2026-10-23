# J-ERP Project Context

This directory is the project's AI memory. It is **derived knowledge**: it
summarizes how J-ERP actually works so an agent can act without re-exploring the
codebase. The source code always wins over this context.

## How To Use It

Before substantial work, read in this order:

1. `config.md` — how this context must be maintained.
2. `structure.md` — which files exist and what belongs in each.
3. The files relevant to the task (see navigation below).
4. The actual source code for the area you are changing.

Do not read every file blindly, and do not trust context over code. If they
conflict, verify the code, correct the context, then continue.

## Files

| File | Contents |
|---|---|
| `config.md` | Update mode, detail level, scope, template |
| `structure.md` | Contract for the context layout |
| `architecture.md` | Purpose, stack, layers, request/render flow, module system, build pipeline |
| `database.md` | PostgreSQL model, per-database registry, declarative schema sync |
| `api.md` | HTTP routes, model API, response/error conventions, uploads |
| `workflows.md` | Run, build, install a module, add a model/page |
| `conventions.md` | Code style, naming, boundaries, safety rules for changes |
| `domains/` | Deeper knowledge for meaningful domains |

## Navigation By Task

| Task | Read |
|---|---|
| Add/change a model or field | `database.md`, `domains/framework.md`, `workflows.md` |
| Drafts, on-change or computed fields | `domains/framework.md`, `domains/ui.md`, `api.md` |
| Add a module, page, or view | `domains/framework.md`, `domains/ui.md`, `workflows.md` |
| Change an endpoint or the model API | `api.md`, `domains/framework.md` |
| Login/session/permissions | `domains/auth.md` |
| Stock / product features | `domains/stock.md` |
| Sales orders and lines | `domains/sale.md` |
| Frontend components or views | `domains/ui.md`, `conventions.md` |
| Build/run/debug | `workflows.md` |

## Ground Rules

- The working directory is the project root (`J-ERP`); commands assume it.
- Do not commit or push unless the user explicitly asks — see `../AGENTS.md`.
- Context is updated **only after approval** (`Update Mode: ask`).
