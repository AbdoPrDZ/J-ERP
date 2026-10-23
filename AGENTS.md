# AGENTS.md

Instructions for AI agents working in this repository.

## Project

**J-ERP** is a small, self-contained ERP platform:

- **Backend:** Python 3.15, standard-library HTTP server, PostgreSQL only
  (`psycopg` 3 + `psycopg_pool`).
- **Frontend:** React 19 + TypeScript + Tailwind CSS 4, built with Vite 8.
- **Modules:** each directory under `modules/` with a `configure.json` is a
  feature module, installed **per database**.
- **Schema:** declarative models + transactional schema synchronization; there
  are no migration files.
- **Views:** a shared React runtime (`runtime.js`) plus per-module ES module
  view bundles built with esbuild and loaded via an import map.

The UI is served from `data/ui`; the backend runs on
`http://127.0.0.1:1347` by default (`jerp.config.json`).

## Project Context — Read First

The AI knowledge layer lives in `.agents/context/`. Before substantial work:

1. Read `.agents/context/README.md`.
2. Read `.agents/context/config.md` and `structure.md`.
3. Read only the files relevant to the task (navigation table in the README).
4. Verify against the actual source; context is derived knowledge and the code
   always wins.

Context update mode is **ask**: when a meaningful change affects project
knowledge, report what changed and which context files are affected, then wait
for approval before editing them. Never rewrite the context wholesale for a
local change.

## Rules

### Git — do not commit or push

- **Do not commit, push, tag, create branches, or open pull requests unless the
  user explicitly asks.**
- Do not run destructive Git commands (reset --hard, clean -f, force push,
  history rewrites) without explicit confirmation.
- Do not initialize a repository or modify Git configuration.
- Leave changes in the working tree and report them.

### Database and data safety

- PostgreSQL is the only supported database. Keep it that way unless asked.
- No database is created at startup; keep the per-database module design.
- Schema sync can **drop columns**; module uninstall **drops tables**. Confirm
  with the user before any destructive database operation.
- Never point changes at production databases or run `DROP DATABASE`/`DROP
  TABLE` against user data without explicit approval.
- `jerp.config.json` holds development credentials. Do not add real secrets.

### Generated files

- Never hand-edit `data/` (built UI, built views, uploads) or `node_modules/`.
  Regenerate with the npm scripts.
- Do not edit `package-lock.json`, `skills-lock.json`, or `.venv/` manually.

### Boundaries

- Framework behavior → `jerp/`.
- Business features, pages, controllers → `modules/<name>/`.
- Build scripts and dev tooling → `tools/`.
- Module views import UI primitives from `@jerp/ui`, never by relative path into
  `jerp/ui` (this would duplicate React).

### Style

- UTF-8, LF, final newline, 2-space indentation.
- Python: single quotes, `from __future__ import annotations`, absolute imports,
  module docstrings, parameterized SQL via `jerp.dialect` quoting.
- TypeScript/React: single quotes, semicolons, functional components, Tailwind
  utility classes.
- Follow the patterns already present in the area you are changing.

### Verification

There is no test suite or linter configured.

- TypeScript: `npm run typecheck`.
- UI shell/kit: `npm run build`.
- Module views: `npm run build:views` (or install/update the module).
- Backend: start `python app.py` and exercise the affected page/API against a
  test database; a compile check catches syntax errors.
- Do not report work as verified unless you actually ran the relevant check.

## Common Commands

```text
python app.py                 # run the backend
python app.py --port 9000     # override the port
npm run dev                   # Vite dev server (needs the backend running)
npm run typecheck             # tsc -b
npm run build                 # UI shell + shared React runtime -> data/ui
npm run build:views           # module view bundles -> data/view
npm run build:all             # both
```

Read `.agents/context/workflows.md` for module installation, adding models,
fields, and pages.
