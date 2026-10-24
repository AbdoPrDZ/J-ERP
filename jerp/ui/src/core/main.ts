import { viewsRegistry } from './registry';
import { loadLocale } from './i18n';
import { beginLoading, endLoading } from './loading';
import { isLoggedIn, readJson, registerBuiltinUtils } from './utils';
import { registerBuiltinFields } from './components/fields';
import { registerBuiltinViews } from './components/views';
import {
  configureSpaNavigation,
  onSpaNavigate,
  resolveTarget,
} from './navigation';

interface PageMeta {
  auth?: boolean;
}

function urlContext(): Record<string, unknown> {
  const params = new URLSearchParams(window.location.search);
  params.delete('name');
  const context: Record<string, unknown> = {};
  params.forEach((value, key) => {
    context[key] = value;
  });
  return context;
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
  const baseContext = readJson<Record<string, unknown>>('__JERP_CONTEXT__', {});

  await loadLocale();

  // Menu links and other internal anchors navigate without reloading the shell.
  configureSpaNavigation({ routes, baseContext });

  const mount = async (
    key: string,
    context: Record<string, unknown>,
  ): Promise<void> => {
    // Mirror the server's login guard (and enforce it in dev).
    const meta = pages[key];
    if (meta && meta.auth !== false && !isLoggedIn()) {
      window.location.assign('/login');
      return;
    }
    if (!viewsRegistry.has(key)) {
      root.textContent = `View "${key}" is not available.`;
      return;
    }

    beginLoading();
    try {
      await viewsRegistry.mount(key, root, context);
    } catch (error) {
      console.error(`Failed to load view "${key}"`, error);
      root.textContent = `Failed to load view "${key}": ${(error as Error).message}`;
    } finally {
      endLoading();
    }
  };

  onSpaNavigate((target) => {
    void mount(target.key, target.context);
  });

  const initialTarget = resolveTarget(new URL(window.location.href));
  const key =
    root.dataset.view || initialTarget?.key || Object.keys(viewUrls)[0];

  if (!key) {
    root.textContent = 'No view registered.';
    return;
  }

  await mount(
    key,
    initialTarget?.context ?? { ...urlContext(), ...baseContext },
  );
}

void boot();
