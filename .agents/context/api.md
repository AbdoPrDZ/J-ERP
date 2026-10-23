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
  `delete`, `fields`.
- Custom methods become callable by decorating them with
  `@jerp.api_expose` (works with `classmethod`/`staticmethod`).
- `all` accepts `domain`, `fields`, `order`, `limit`, `offset`; a domain is a
  list of `(field, operator, value)` leaves (`=`, `!=`, `>`, `<`, `in`,
  `like`, `ilike`, `is null`, …) combined with AND.
- Errors: `no_database` (400), `unknown_model` (404), `unknown_method` (404),
  `bad_arguments` (400), `call_failed` (400).

## Database Scoping

- The active database comes from the `jerp_db` cookie or the `X-JERP-DB`
  header, resolved by `jerp.http.middleware.database_scope` per request.
- The active name is stored in a `ContextVar`; no database selected raises an
  error, and the model API returns `no_database`.
- HTML requests whose cookie points at a removed database are redirected to
  `/db/manager` and the cookie cleared.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/login`, `POST /api/logout` | Credential check, session cookie |
| `GET/POST /api/databases` | List / create databases (creation installs core and seeds an admin user) |
| `POST /api/databases/select` | Set the `jerp_db` cookie |
| `POST /api/model/<model>/<func>` | Model API |
| `POST /api/upload`, `POST /api/upload/confirm` | Store file to tmp, then confirm and create a `file` record |
| `GET /__storage/<name>` | Serve a stored file (outside `/api`) |
| `/__endpoints` | URL prefixes consumed by the Vite dev proxy |

Database names are validated as `^[a-z_][a-z0-9_]{0,62}$`.

## Pages And Auth

- Pages are declared in each module's `configure.json` under `routes` (page
  entries need `view`; groups use `label` + `children`).
- A page with `endpoint` becomes a server route; pages without one are served by
  `/view?name=<view>`.
- Page routes default to `auth: true`: without a `jerp_user` cookie the request
  is redirected to `/login`. Set `"auth": false` for public pages.
- The router stores an `auth` flag for API routes, but dispatch does **not**
  enforce it centrally; authorization for API endpoints is currently absent.
  Do not assume the model API is protected beyond the login page flow.
- Session identity is the presence of the `jerp_user` cookie; the login handler
  verifies credentials against the selected database's `users` table.
