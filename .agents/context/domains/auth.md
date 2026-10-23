# Domain: Authentication

## Purpose

Minimal, database-backed login. There is no user table in the framework; the
`users` model belongs to the `core` module and exists only in databases where
core is installed.

## Important Entities

- `modules/core/models/user.py` → model `sys.user`, table `sys_user`
  - `name` (display name), `username` (login, unique + indexed),
    `password` (hidden, PBKDF2 hash), `image` (file reference).
- `jerp.security` → PBKDF2-SHA256 hashing (`pbkdf2_sha256$<iters>$<salt>$<hash>`)
  with 260,000 iterations and constant-time verification.

## Flows

### Login

1. Client posts `{username, password}` to `/api/login`.
2. `AuthController` searches `sys.user` by username in the **active database**.
3. `check_password` verifies the PBKDF2 hash; failure returns 401
   `invalid_credentials`.
4. Success sets `jerp_user=<username>` (path `/`, `SameSite=Lax`) and returns
   `{"user": <display name>}`.

### Logout

`/api/logout` clears `jerp_user` with `Max-Age=0`.

### Guarding pages

- `jerp.routes` redirects to `/login` when a page with `auth: true` has no
  `jerp_user` cookie.
- The client mirrors the check in `main.ts` using the same cookie.
- `auth: false` pages (login, database manager) are public.

### User creation

Passwords are hashed in `User.create` and `User.write` whenever a raw value is
supplied; existing hashes are left untouched. Creating a database seeds an admin
user with the supplied password.

## Current Limits (important)

- **No session store or tokens.** Authentication is exactly "the `jerp_user`
  cookie exists"; it can be forged and is not validated per request.
- **No per-user authorization or roles.** Any logged-in cookie can call the
  model API; the router's `auth` metadata is not enforced during dispatch.
- **No CSRF protection and no cookie signing.** Treat the app as a trusted-LAN
  tool until this changes.

Do not claim or implement security guarantees that the code does not provide;
if hardening auth, treat it as an architectural change to be approved first.
