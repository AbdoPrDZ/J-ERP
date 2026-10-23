# Domain: UI Kit And View Pipeline

## Purpose

A shared React UI kit (`jerp/ui/src/core`) is shipped once as `runtime.js`; each
module supplies only its views. Views are plain ES modules loaded at runtime, so
no rebuild of the shell is needed when a module's views change.

## Important Pieces

- `jerp/ui/src/core/runtime.ts` — public surface of `@jerp/ui`: `App`, `Page`,
  form/table/cards/action primitives, `model()`, `api`, `viewsRegistry`,
  field/view registries, utils and types. Anything modules import must be
  re-exported here.
- `main.ts` — bootstraps: registers built-in fields/views/utils, registers view
  URLs from `__JERP_VIEWS__`, resolves the view key, guards auth, mounts.
- `registry.tsx` — `viewsRegistry`: key → dynamic `import()` loader; mounts the
  view inside `App` into the `#root` element (one root per element).
- `App.tsx` — shell: header/menus/user menu; reads `__JERP_MENUS__` and
  `__JERP_PAGES__`; renders `<View context={context} />` inside `<main>`.
- `model.ts` / `api.ts` — typed client for `POST /model/<name>/<func>` and the
  `/api` fetch wrapper (same-origin credentials, JSON errors).
- `components/page/` — page composition: `Page` (view/id query params, header,
  breadcrumb, view switcher), `Table`, `Cards`, `Form`, `Action`.
- `components/views/` — descriptor-driven standard views (`table`, `form`,
  `cards`) registered in `viewRegistry`, used with `/view?model=…&type=…`.

## View Runtime Contract

- A module view is `modules/<module>/ui/src/views/<Name>.tsx` with a default
  export component accepting `{ context }`.
- esbuild compiles it to `data/view/<module>/<Name>.js`, externalizing `react`,
  `react-dom*` and `@jerp/ui`.
- `manifest.json` maps `<module>.<snake_case_file>` → relative JS path.
- The server exposes these at `/views/<module>/…` and injects the map into the
  shell. The import map resolves `@jerp/ui` and React to the shared bundles.

## Page Query Convention

- `?view=list|cards|form` selects the page view; `?id=<id>` opens a record.
- `navigateTo()` merges query params, keeping the pathname.
- `Page` derives `view` from the query, defaults to `views[0]`, and renders the
  breadcrumb/record label.

## Constraints

- Never import React or `@jerp/ui` through relative paths from modules — the
  bundle would duplicate React.
- Add shared components to the kit and re-export them from `runtime.ts`.
- Keep server-injected payload IDs (`__JERP_*`) stable; the shell and server
  agree on them.
- Rebuild views after edits: `npm run build:views` (or install/update the
  module). Rebuild the shell/kit with `npm run build`.
- Styling is Tailwind utility classes; keep the existing slate/blue palette.
