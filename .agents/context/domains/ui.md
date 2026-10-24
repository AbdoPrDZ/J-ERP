# Domain: UI Kit And View Pipeline

## Purpose

A shared React UI kit (`jerp/ui/src/core`) is shipped once as `runtime.js`; each
module supplies only its views. Views are plain ES modules loaded at runtime, so
no rebuild of the shell is needed when a module's views change.

## Important Pieces

- `jerp/ui/src/core/runtime.ts` — public surface of `@jerp/ui` and
  `@jerp/locale`: `App`, `Page`, form/table/cards/action primitives, `model()`,
  `api`, `viewsRegistry`, `t`/`useLocale`, field/view registries, utils and
  types. Anything modules import must be re-exported here.
- `main.ts` — bootstraps: loads the locale catalog, registers built-in
  fields/views/utils, registers view URLs from `__JERP_VIEWS__`, resolves the
  view key, guards auth, mounts.
- `registry.tsx` — `viewsRegistry`: key → dynamic `import()` loader; mounts the
  view inside `App` into the `#root` element (one root per element).
- `navigation.ts` — SPA router: intercepts same-origin anchors, resolves `/view`,
  `/page/<key>` and registered routes, pushes history and remounts the view.
- `loading.ts` — reference-counted loading store for API requests/view mounts;
  drives the delayed top bar and header spinner.
- `App.tsx` — shell: header/menus/user menu; reads `__JERP_PAGES__`, fetches
  menus via `useMenu()` (`GET /api/menu`). Renders `<View>` inside `<main>`;
  drawer/link/view transitions are animated.
- `i18n.ts` — `t(key, params?)`, `setLocale()`, `loadLocale()` and `useLocale()`.
  `t()` has no English fallback argument; missing keys fall back to the default
  catalog, then the key.
- `model.ts` / `api.ts` — typed client for `POST /model/<name>/<func>` and the
  `/api` fetch wrapper (same-origin credentials, JSON errors); includes the
  draft API (`newDraft`, `editDraft`, `changeDraft`, `drafts`, `commitDrafts`).
- `draft.ts` — per-form session token, `DraftQueue` with an 800 ms debounce,
  flush on Save, and draft-token cleanup after commit.
- `components/page/` — page composition: `Page` (view/id query params, header,
  breadcrumb, view switcher), `Table`, `Cards`, `Form`, `FormTable`, `Action`,
  and `PlanDialog` (schema plan preview/confirmation for table actions).
- A `Table` action may declare `preview` (a read-only model method) and
  `allow_drop`; the table then opens `PlanDialog`, which loads the plan, offers
  the database-wide drop only when allowed, and applies the action on confirm.
- `Form` and `FormTable` edit server drafts: parent and child rows share a token,
  rows use `reuse: false`, inline cell editing sends changes through the draft
  queue, and parent computed values refresh when child drafts change.
- `Many2oneField` lists real records plus drafts from the same session token.
- Computed fields are read-only from the schema and display model-computed values.
- `components/views/` — descriptor-driven standard views (`table`, `form`,
  `cards`) registered in `viewRegistry`, used with `/view?model=…&type=…`.

## View Runtime Contract

- A module view is `modules/<module>/ui/src/views/<Name>.tsx` with a default
  export component accepting `{ context }`.
- esbuild compiles it to `data/view/<module>/<Name>.js`, externalizing `react`,
  `react-dom*`, `@jerp/ui` and `@jerp/locale`.
- `manifest.json` maps `<module>.<snake_case_file>` → relative JS path.
- The server exposes these at `/views/<module>/…` and injects the map into the
  shell. The import map resolves `@jerp/ui` and React to the shared bundles.
- In Vite dev the plugin registers source view URLs and filters modules using
  `GET /__modules` (selected database); uninstalled modules must not appear in
  the menu or view map.
- `build:views` recurses into subdirectories and fails if a declared menu view
  has no matching file.
- User-facing strings use `t('view.<module>.<view>.<key>')` from
  `@jerp/locale`. The module's `i18n/en.lang` must contain the English value;
  `i18n scaffold` collects literal `t()` calls from `.ts`/`.tsx`.

## Page Query Convention

- `?view=list|cards|form` selects the page view; `?id=<id>` opens a record.
- `navigateTo()` merges query params and routes through `openHref()`; internal
  navigation does not reload the document.
- `Page` derives `view` from the query, defaults to `views[0]`, and renders the
  breadcrumb/record label.

## Home And Branding

- The Home dashboard computes contact/order/product/user counts from installed
  models only. Quick-access links and `add_to_home` are currently removed.
- Login uses `modules/core/ui/assets/logo-full.png`, a split brand/form layout and
  a password visibility toggle. Its strings are translated via `t()`.
- The database manager is intentionally **English-only** because it renders
  before a database/catalog exists; do not add `t()` there.
- `public/favicon.ico` is linked from `public/index.html`; the Vite dev shell maps
  `/favicon.ico` to it.
- Home, login and technical pages live under `views/pages/`; the view key uses the
  file basename, so `views/pages/Home.tsx` → `core.home`.

## Constraints

- Never import React or `@jerp/ui` through relative paths from modules — the
  bundle would duplicate React.
- Add shared components to the kit and re-export them from `runtime.ts`.
- Keep server-injected payload IDs (`__JERP_*`) stable; menus/models/i18n are
  fetched from their APIs instead of injected.
- Rebuild views after edits: `npm run build:views` (or install/update the
  module). Rebuild the shell/kit with `npm run build`.
- Run `python -m jerp.cli i18n check` after changing `t()` keys or `.lang` files.
- Styling is Tailwind utility classes; keep the existing slate/blue palette.
