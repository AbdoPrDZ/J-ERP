# J-ERP Review: Weaknesses and Improvements

Oct 23, 2026 · @Abderrahmane GUERGUR

## Scope and what holds up

This review covers the framework core and the `core`, `sale` and `stock` modules of [J-ERP](https://github.com/AbdoPrDZ/J-ERP) at commit 22440d9, and its 40 unit tests pass (run here on Python 3.13). I did not read all of `models.py` (2,585 lines) or every UI component, so those parts are less certain.

The SQL layer is solid: queries are parameterized, identifiers go through `quote_ident`, static files have a path-traversal check, and DDL runs transactionally. The weak points are elsewhere.

## Critical: there is effectively no authentication or authorization

Anyone who can reach the port can read, change or delete any data, and can reinstall or uninstall modules.

- **The model API is open.** `POST /api/model/<model>/<func>` (`modules/core/controller/model_api.py`) is registered with `auth=False`, and `Router.dispatch` never checks the `auth` flag anyway. That includes `sys.user`: `hide=True` on `password` only hides it on reads, so anyone can overwrite an admin's password.
- **The API can change the system itself.** `module.install`, `update` and `uninstall` are exposed through the same unauthenticated API, and uninstall drops tables.
- **The login "session" is a plain cookie.** `/login` sets `jerp_user=<username>` with no signature, no server-side session, and no `HttpOnly` or `Secure`. Page gating only checks that the cookie exists, so setting `jerp_user=x` in the browser gets past it. There is no rate limiting on login. The README roadmap lists session auth, but it should come before any other feature.
- **No permissions model.** There are no access rights or record rules, so every user has full CRUD on everything.
- **The client picks the database.** The `jerp_db` cookie or `X-JERP-DB` header chooses it. `/databases/select` validates the name, but `database_scope` in the middleware does not re-check it against the owner-scoped list.
- **Uploads can cause stored XSS.** `/upload/confirm` accepts the client's `mimetype`, and `/__storage/<name>` serves the file back from the same origin with that type, so an uploaded HTML or SVG file runs in the app's origin. There is no size limit, no `nosniff` header, and `_read_body` loads the whole body into memory.
- **Errors leak internals.** Several endpoints return `str(exc)` to the client, exposing SQL and internal details.

**Fixes**

1. Use server-side sessions, or signed tokens, in an `HttpOnly; SameSite` cookie. Enforce auth in the router, deny by default, and require an explicit `public=True` for open routes.
2. Add groups, per-model ACLs and record rules, and require an admin group for module and database operations.
3. Whitelist upload types, cap the size, force `Content-Disposition: attachment` for non-images, and send `nosniff`.
4. Return generic errors to clients and log the details.

## Schema sync ("no migrations") is the riskiest design choice

The sync can silently move or destroy data, and it runs live with no preview.

- **Silent renames.** In `_apply_renames`, any declared field with no column is matched to any removed field whose column still exists. Remove `discount` and add `margin` in one release, and the sync renames the column, so `margin` now holds `discount`'s data (with a cast if the types differ).
- **Silent data loss.** `_apply_drops` drops the column whenever a field disappears from code.
- **Live DDL with no preview.** The sync runs directly on whichever database you press "Update" on, with no dry run, no diff, no backup, and no way to run a data transformation.
- **No review trail.** Schema changes can't be reviewed in a pull request, because the diff only exists at runtime.

**Fixes**

1. Keep the declarative diff, but use it to generate reviewable migration files with explicit renames and drops.
2. At minimum, make sync dry-run by default, refuse destructive operations without a flag, and require an explicit `renamed_from='old'` on fields.

## ORM and data layer

Writes are not atomic, money is stored as a float, and the core file has grown too large.

- **Writes aren't atomic.** Transactions appear in only two places in the code (the draft commit paths in `models.py`). `create()` does an insert, `register_ref`, translations and recompute as separate autocommitted statements, so a failure midway leaves partial data. Wrap every API call in one transaction.
- **Domains are AND-only.** `_build_where` has no OR, NOT, nesting or dotted paths, which will hurt as soon as you build real search or reporting.
- **Money is a float.** `FloatField` is used for `price`, `amount_total`, `subtotal` and `margin`. Use `Decimal`, and add currency and rounding rules. A `NumericField` already exists.
- **One pool per database.** Each tenant database gets its own pool of up to 10 connections and its own in-memory registry, and none are ever evicted. That is fine for 5 databases and breaks at 200.
- **`models.py` does too much.** The 2,585-line file holds the metaclass, ORM, drafts, computed fields, i18n and API exposure. HTTP exposure belongs in a separate layer.

## Server and operations

The app cannot be deployed safely as it stands.

- **Not production-safe.** It runs on stdlib `ThreadingHTTPServer`, with unbounded threads, no TLS, no timeouts and no compression. Put a proper ASGI server behind a reverse proxy (FastAPI, Starlette or Litestar, with uvicorn).
- **Needs Node at runtime.** `build_views` shells out to `node` at install time from `Path.cwd()`, so the app only works when launched from the repo root and needs Node in production. Build the view bundles in CI or at image build time.
- **Modules are trusted code.** They are imported in-process with no isolation, and `depends` carries no version constraints. That is fine for a first-party monorepo, but state clearly that third-party modules aren't supported yet.
- **No deployment story.** There is no Dockerfile, compose file or CI.
- **Python 3.15 is required, but nothing seems to need it.** The tests passed on 3.13. Lowering the minimum costs nothing and widens who can run it.

## ERP scope

Only two business modules exist: `stock` (one model, `product`) and `sale` (order and order line). There is no accounting, stock moves or locations, purchasing, invoicing, tax, numbering sequences, audit trail, reports or PDFs, import/export, or background jobs. Build these on a solid core rather than growing the UI first.

## Repo hygiene

Several small inconsistencies add friction for new users and contributors.

- `package.json` says license ISC; the repo is Apache-2.0.
- `AGENTS.md` says "There is no test suite," but `tests/` has 40 passing tests. They are unit-level only, with no HTTP or database integration tests.
- The README quickstart never says to copy `jerp.config.json.example`, and the config table omits `security.master_key`. Without it, creating a database returns 503, so new users hit a wall at step one.
- The repo has a single commit, a `.agents/` knowledge folder that will go stale, and no linter or type checker for Python.

## How I'd build it

I would keep the good ideas (per-database modules, declarative models, server-side drafts, module-declared menus and views) and change the foundations:

1. **Core first.** Sessions, users, groups, ACLs and record rules, with every request in one transaction, before any feature.
2. **Migrations.** Auto-diff generates migration files that a human reviews; destructive changes need an explicit step.
3. **Server.** An ASGI framework with Pydantic-validated requests, and explicit whitelisted RPC methods instead of "everything with `@api_expose`" behind one catch-all endpoint.
4. **Frontend.** TypeScript types and clients generated from the model metadata, and view bundles built in CI.
5. **Money and quantities.** `Decimal` everywhere, plus a currency model.
6. **Tests.** Integration tests against a real Postgres in CI, covering auth, permissions and schema sync, which are the parts that can destroy data.
7. **Packaging.** A Docker image with the built UI baked in, and Postgres in compose.

## What to do this week

Start with the changes that stop data loss and unauthorized access.

1. Enforce auth in the router and replace the cookie with real sessions.
2. Lock down uploads and stop returning raw exceptions.
3. Make schema sync non-destructive by default, with explicit renames.
4. Fix the README quickstart and the license mismatch.
