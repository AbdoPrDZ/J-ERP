import { viewsRegistry } from './registry';
import { isLoggedIn, readJson, registerBuiltinUtils } from './utils';
import { registerBuiltinFields } from './components/fields';
import { registerBuiltinViews } from './components/views';

interface PageMeta {
  auth?: boolean;
}

/** Resolve the view to mount from the URL: `/page/<name>`, `/view?name=`, or a route. */
function viewKeyFromRoute(routes: Record<string, string>): string | null {
  const { pathname, search } = window.location;

  const pageMatch = pathname.match(/^\/page\/(.+)$/);
  if (pageMatch) {
    return decodeURIComponent(pageMatch[1]);
  }

  if (pathname === '/view') {
    const name = new URLSearchParams(search).get('name');
    if (name) {
      return name;
    }
  }

  return routes[pathname] ?? null;
}

async function boot(): Promise<void> {
  registerBuiltinFields();
  registerBuiltinViews();
  registerBuiltinUtils();

  // Views are provided by the server (installed modules) as name -> url.
  const viewUrls = readJson<Record<string, string>>('__JERP_VIEWS__', {});
  for (const [key, url] of Object.entries(viewUrls)) {
    viewsRegistry.register(key, () => import(/* @vite-ignore */ url));
  }

  const root = document.getElementById('root');
  if (!root) {
    return;
  }

  const routes = readJson<Record<string, string>>('__JERP_ROUTES__', {});
  const pages = readJson<Record<string, PageMeta>>('__JERP_PAGES__', {});

  // Merge URL query params into the context (the server does this in prod; in
  // dev the shell is served by Vite, so the client fills it in).
  const params = new URLSearchParams(window.location.search);
  params.delete('name');
  const urlContext: Record<string, unknown> = {};
  params.forEach((value, key) => {
    urlContext[key] = value;
  });
  const context = {
    ...urlContext,
    ...readJson<Record<string, unknown>>('__JERP_CONTEXT__', {}),
  };

  const key =
    root.dataset.view || viewKeyFromRoute(routes) || Object.keys(viewUrls)[0];

  if (!key) {
    root.textContent = 'No view registered.';
    return;
  }

  // Mirror the server's login guard (and enforce it in dev).
  const meta = pages[key];
  if (meta && meta.auth !== false && !isLoggedIn()) {
    window.location.assign('/login');
    return;
  }

  try {
    await viewsRegistry.mount(key, root, context);
  } catch (error) {
    root.textContent = `Failed to load view "${key}": ${(error as Error).message}`;
    throw error;
  }
}

void boot();
