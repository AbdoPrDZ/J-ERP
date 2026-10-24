# API

## Shape

- HTTP server: standard-library `ThreadingHTTPServer` (`jerp.server`).
- Routers are registered with decorators (`@router.get('/x')`,
  `@router.post`, `@router.route('/')`) from classes deriving
  `jerp.http.controller.Controller`.
- Routes are discovered by importing `modules.<name>.controller` packages, then
  re-registered as **bound** methods. Endpoints may contain `<name>` segments.
- Clients always use the `/api` prefix; the server strips it before dispatch.
- JSON responses use `jerp.http.response.json`; pages use `response.render`;
  redirects use `response.redirect`. Errors are JSON
  `{"error": "<code>", "message": "<human text>"}` with a 4xx/5xx status.

## Model API

`POST /api/model/<model_name>/<func>` with a JSON object body; keys become
keyword arguments.

- Response: `{"result": <value>}`.
- Standard exposed methods: `all`, `count`, `find`, `create`, `update`,
  `delete`, `delete_many`, `fields`.
- Draft methods: `new`, `edit`, `change`, `drafts`, `discard`, `discard_all`,
  `remove`, `save`, `commit`.
  - `new` without a token is Python-only (in-memory record); over HTTP the UI
    always sends a token. `new` accepts `reuse: false` to create a second row
    draft for the same token.
  - `change` accepts `{draft_id, values}` and returns `values`, `dirty`, `errors`,
    `warnings`, `domains`, `version`.
  - `commit` accepts `{token, parent_field?, parent_id?}` and writes all drafts
    in the token atomically.
- Custom methods become callable by decorating them with
  `@jerp.api_expose` (works with class/static methods and instance methods).
- Instance methods receive the record identified by `id` (or `draft_id`) in the
  body; `confirm(self)` in the sale module is an example. They may set fields
  directly; assignments on persisted records are written immediately.
- `create` accepts a positional dictionary in Python and keyword arguments over
  HTTP. Many2one values may be records, ids or `draft:<id>` references.
- `all` accepts `domain`, `fields`, `order`, `limit`, `offset`; a domain is a
  list of `(field, operator, value)` leaves (`=`, `!=`, `>`, `<`, `in`,
  `like`, `ilike`, `is null`, …) combined with AND.
- Computed fields are returned by `all`/`find` (evaluated on read) but are
  read-only in the field schema.
- Errors: `no_database` (400), `unknown_model` (404), `unknown_method` (404),
  `bad_arguments` (400), `call_failed` (400).
- `delete`/`delete_many` refuse records still referenced by a many2one or
  file/image field. The API returns `call_failed` with a message naming the
  blocking model/field; bulk deletes are transactional.
- `fields`/`all`/`find` metadata labels, help and selection labels are
  translated server-side from `sys.translation` for the current language.
- `GET /api/search?model=<model>&q=<text>` searches one model's display labels;
  it is used by the command palette. `GET /api/models` returns the available
  model -> page map and is never cached.

## Database Scoping And Language

- The active database comes from the `jerp_db` cookie or the `X-JERP-DB`
  header, resolved by `jerp.http.middleware.database_scope` per request.
- The active name is stored in a `ContextVar`; no database selected raises an
  error, and the model API returns `no_database`.
- HTML requests whose cookie points at a removed database are redirected to
  `/db/manager` and the cookie cleared.
- Language resolution is per user: `sys.user.lang_id` (when active), then the
  `jerp_lang` cookie, then `sys.lang.is_default`, then `en`.
- New databases have only English active. `POST /api/lang` saves the user's
  choice and sets `jerp_lang`; `GET /api/i18n` returns the catalog, direction,
  fallback catalog and active languages with `Cache-Control: no-store`.
- `sys.lang.write(active=True)` loads that language's `.lang` files for all
  installed modules.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/login`, `POST /api/logout` | Credential check, session cookie |
| `GET/POST /api/databases` | List / create databases (creation installs core and seeds an admin user) |
| `POST /api/databases/select` | Set the `jerp_db` cookie |
| `POST /api/databases/delete` | Force-drop a database (master key required; admin role optional) |
| `POST /api/model/<model>/<func>` | Model API |
| `GET /api/menu` | Nested menu tree from `sys.menu` for the active database, no-store |
| `GET /api/models` | Model -> page map for search, no-store |
| `GET /api/i18n` | Active language catalog, direction and active languages, no-store |
| `POST /api/lang` | Save the user language preference and set `jerp_lang` |
| `GET /api/search` | Search one model's record labels |
| `POST /api/upload`, `POST /api/upload/confirm` | Store file to tmp, then confirm and create a `file` record |
| `GET /__storage/<name>` | Serve a stored file (outside `/api`) |
| `/__endpoints` | URL prefixes consumed by the Vite dev proxy |
| `/__modules` | Installed module names for the dev shell (uses `jerp_db`) |

Database names are validated as `^[a-z_][a-z0-9_]{0,62}$`.

Database deletion first terminates the application's own sessions. If a
superuser session (for example pgAdmin) remains and `databases.admin_user` is
configured, it uses that role to `DROP DATABASE ... WITH (FORCE)`; otherwise it
returns `409 database_in_use` with the blocking sessions.

## Pages And Auth

- Pages are declared in each module's `configure.json` under `routes` (page
  entries need `view`; groups use `label` + `children`).
- Page/route options: `label`, `view`, `endpoint`, `params`, `sequence`, `img`,
  `description`, `auth`, `header`, `menu`, `drawer`, `hide`.
- Labelled, non-hidden entries are synchronized into `sys.menu` on
  install/update and served by `GET /api/menu`. `add_to_home` is currently
  ignored; the Home dashboard no longer renders quick-access links.
- A page with `endpoint` becomes a server route; pages without one are served by
  `/view?name=<view>`.
- Page routes default to `auth: true`: without a `jerp_user` cookie the request
  is redirected to `/login`. Set `"auth": false` for public pages.
- The router stores an `auth` flag for API routes, but dispatch does **not**
  enforce it centrally; authorization for API endpoints is currently absent.
  Do not assume the model API is protected beyond the login page flow.
- Session identity is the presence of the `jerp_user` cookie; the login handler
  verifies credentials against the selected database's `sys_user` table, adopts
  a valid language preference (or the `jerp_lang` cookie) and returns `lang`.
- The user menu language selector posts `/api/lang`, which updates
  `sys.user.lang_id` when logged in and sets `jerp_lang`.
