I’ve received the new J-ERP source archive and started reviewing the actual code, rather than relying on the previous review. This version has grown substantially: it now includes a custom HTTP layer, a PostgreSQL ORM, module lifecycle APIs, file uploads, and a React/TypeScript frontend.
Initial findings: security comes first
The most urgent issue is that the backend does not enforce authentication consistently. Several API routes rely on the frontend hiding pages or controls, but that is not a security boundary.

In particular, the model API allows callers to invoke exposed model methods, and the module model exposes installation, update, and uninstallation operations. I’m checking the consequences and the schema/module lifecycle code next so the review distinguishes confirmed vulnerabilities from design recommendations.
Confirmed high-priority issues in this snapshot

1. Critical — Login can be bypassed
Files: modules/core/controller/auth.py, modules/core/controller/entrypoint.py, jerp/ui/src/core/utils/index.ts

The application treats the presence of a jerp_user cookie as proof of login. The cookie is set to the username, not a server-validated session identifier or signed token. A client can fabricate this cookie and pass the UI and page-level login checks without supplying a password.

Impact: Access to pages intended for authenticated users. This becomes more serious because the backend APIs also lack consistent authorization checks.

Fix: Use server-validated sessions with unpredictable identifiers, expiration, revocation, and HttpOnly, Secure (under HTTPS), and appropriate SameSite cookie settings. Never authorize a request based only on a client-supplied username.




2. Critical — Model API permits unauthenticated data access and modification
Files: modules/core/controller/model_api.py, jerp/models.py

ModelApiController.call() checks whether a model and exposed method exist, but it does not check whether the caller is authenticated or authorized for that model, record, operation, or field. The standard exposed methods include all, find, create, update, delete, and delete_many.

Impact: A caller may read or alter business records, create accounts, change user passwords, or delete records without going through the intended UI.

Fix: Enforce authentication and authorization centrally on the server. Define model-, operation-, record-, and field-level permissions, and explicitly restrict sensitive operations such as password changes. Hiding a field in the UI or excluding it from normal serialization is not an authorization policy.




3. Critical — Module lifecycle operations are exposed through the same API
Files: modules/core/models/module.py, modules/core/controller/model_api.py, jerp/registry.py, jerp/modules.py

The sys.module model exposes install, update, and uninstall, and the generic model API can invoke exposed methods without a permission check. Uninstallation can drop the tables belonging to a module.

Impact: An unauthenticated caller may be able to trigger destructive module operations, potentially removing business tables and their data. The precise damage depends on which modules are installed and their model definitions.

Fix: Treat module lifecycle operations as privileged administration actions, not ordinary CRUD. Require administrator authorization, audit each operation, preview schema changes, and require explicit confirmation for destructive actions. Consider a separate administrative service/API rather than exposing these methods through the generic model endpoint.




4. High — Upload endpoints have no visible size or rate limits
Files: jerp/server.py, modules/core/controller/upload.py, jerp/uploads.py

The HTTP handler reads the declared Content-Length into memory, and the upload endpoint writes the received bytes to temporary storage. I found no request-body size limit, upload quota, or rate limit in these paths.

Impact: Large uploads or repeated requests can consume memory and disk space, degrading or taking down the service.

Fix: Reject oversized bodies before reading them, enforce a configurable upload limit and per-user quota, rate-limit uploads, and expire abandoned temporary files. Also add request read timeouts and appropriate limits at the reverse proxy.



These are code-level findings from the uploaded snapshot. I have not performed a live penetration test against a running instance.
Additional findings: schema safety and framework behavior

5. High — Automatic field renaming can move the wrong data
File: jerp/schema.py, _apply_renames()

When a declared field's column is missing, the code selects the first stored field that is no longer declared and whose old column still exists. It does not require an explicit old-to-new field mapping.

Failure scenario: A model removes address and adds description. The syncer may rename the old address column to description, preserving the wrong values while losing the intended meaning of the data. Subsequent drop logic may remove other columns that are no longer declared.

Fix: Require explicit rename metadata such as renamed_from='address'. Treat unmatched removals and additions as separate operations, and make destructive drops opt-in. Provide a schema diff/preview before applying changes.




6. High — Uninstallation is not atomic across a module
Files: jerp/modules.py, jerp/schema.py, jerp/registry.py

ModuleManager.uninstall() drops each model's table through a separate transaction, then deletes the module registry entry. If a later table drop or registry update fails, earlier tables may already be gone while the module still appears installed.

Fix: Plan the complete uninstall first, then execute the database changes and registry update in one transaction where possible. Where a single transaction is impractical, implement a staged lifecycle with explicit states, recovery handling, and a dry-run preview. Backups are essential before destructive operations.




7. Medium — Dependency cycles are not explicitly detected
File: jerp/modules.py, resolve_order()

The resolver uses a seen set to avoid revisiting modules, but it does not track the active recursion path. A dependency cycle can therefore be treated as if the dependency has already been handled rather than rejected as a cycle.

Fix: Use three traversal states—UNVISITED, VISITING, and VISITED—and raise a clear error if traversal reaches a VISITING module. Add tests for direct cycles (A → A) and indirect cycles (A → B → A).




8. High — Route-level auth metadata is stored but not enforced by the router
File: jerp/http/router.py

Routes can be registered with auth=True, and the router stores that flag. However, Router.dispatch() invokes the handler without checking it. That means future developers may mark a route as protected and reasonably assume it is guarded, when the framework does not actually enforce that policy.

Fix: Make authentication enforcement part of dispatch, backed by the server-side session system. Define explicit public routes and default to requiring authentication for protected API routes. Add tests proving that unauthenticated requests to an auth=True route are rejected.



A useful improvement already present in this version: SchemaSyncer.sync_models() wraps the schema synchronization of its supplied models in a single transaction. That is a good foundation, but it does not make the entire module install/update/uninstall workflow atomic.
Verification results
I ran the checks that were possible in this environment.
Check	Result
Python syntax compilation (compileall)	Passed
Python unit tests	Blocked
Frontend typecheck/build	Not run
Live PostgreSQL integration tests	Not run

The Python tests cannot currently collect because psycopg is not installed in this environment. The frontend dependencies (node_modules) are also absent, so I could not run the TypeScript check or Vite/esbuild builds. Syntax compilation passing does not establish that the application works correctly at runtime.
Recommended repair order
I would pause new feature development briefly and address these in order:
1. Close the authorization gap first. Implement real server-side sessions and a centralized permission layer. Protect model CRUD, custom exposed methods, temporary-record operations, file confirmation/storage, and module lifecycle actions. Do not rely on a cookie-presence check.
2. Protect destructive operations. Add schema dry-run output, explicit field rename/drop declarations, and safer uninstall behavior. Take a verified backup before testing any schema change or uninstall against a database with real data.
3. Harden HTTP and uploads. Enforce body-size limits, request timeouts, upload quotas, login throttling, and safer error responses that do not return internal exception details to clients.
4. Add regression tests for framework guarantees. Cover authorization, cross-database request isolation, schema rollback/data preservation, dependency cycles, and module install/update/uninstall failure recovery.
5. Then validate the full stack. Install the pinned Python and npm dependencies in a clean environment, run the unit suite and frontend checks, and exercise the APIs against a disposable PostgreSQL database.
Overall assessment
J-ERP has a useful foundation: the per-database registry, declarative ORM, transactional schema synchronization, and shared React runtime are coherent directions for a modular ERP. The main architectural concern is that the security boundary is not yet aligned with the model/API boundary. The generic API and module system can perform privileged operations, but the current backend does not consistently require the permissions those operations need.

My recommendation is to treat authentication and authorization as a prerequisite to further expansion, followed by schema migration safety. Those two areas carry the greatest risk of unauthorized access or irreversible data loss.

This review covers the uploaded archive, not a live deployment or the latest GitHub state beyond that archive.
