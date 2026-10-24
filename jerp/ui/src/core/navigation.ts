/**
 * Client-side navigation for the J-ERP shell.
 *
 * Menu links and other same-origin anchors are handled here: they update the
 * URL with the History API and hand the resolved view key to the shell instead
 * of asking the server for a new HTML document.
 */

export interface NavigationTarget {
  key: string;
  context: Record<string, unknown>;
}

interface NavigationOptions {
  routes: Record<string, string>;
  baseContext?: Record<string, unknown>;
}

let routes: Record<string, string> = {};
let baseContext: Record<string, unknown> = {};
let handler: ((target: NavigationTarget) => void) | null = null;
let configured = false;

function contextFromSearch(search: string): Record<string, unknown> {
  const params = new URLSearchParams(search);
  params.delete('name');
  const context: Record<string, unknown> = {};
  params.forEach((value, key) => {
    context[key] = value;
  });
  return context;
}

/** Resolve a same-origin URL to a registered view, or ``null`` for server pages. */
export function resolveTarget(url: URL): NavigationTarget | null {
  let key: string | null = null;

  if (url.pathname === '/view') {
    key = url.searchParams.get('name');
  } else {
    const page = url.pathname.match(/^\/page\/(.+)$/);
    key = page ? decodeURIComponent(page[1]) : (routes[url.pathname] ?? null);
  }

  if (!key) {
    return null;
  }
  return {
    key,
    context: { ...contextFromSearch(url.search), ...baseContext },
  };
}

function emit(target: NavigationTarget): void {
  handler?.(target);
}

function emitCurrentLocation(): void {
  const target = resolveTarget(new URL(window.location.href));
  if (target) {
    emit(target);
  } else {
    // Back/forward landed on a page that only the server can render.
    window.location.reload();
  }
}

function onClick(event: MouseEvent): void {
  if (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  ) {
    return;
  }

  const element = event.target as Element | null;
  const anchor = element?.closest('a');
  if (!anchor || anchor.target || anchor.hasAttribute('download')) {
    return;
  }

  const href = anchor.getAttribute('href');
  if (!href || href.startsWith('#')) {
    return;
  }

  const url = new URL(href, window.location.href);
  if (url.origin !== window.location.origin) {
    return;
  }
  if (!resolveTarget(url)) {
    return;
  }

  event.preventDefault();
  openHref(url.href);
}

/**
 * Enable SPA navigation. Safe to call once from the shell bootstrap.
 */
export function configureSpaNavigation(options: NavigationOptions): void {
  routes = options.routes ?? {};
  baseContext = options.baseContext ?? {};

  if (configured) {
    return;
  }
  configured = true;
  document.addEventListener('click', onClick);
  window.addEventListener('popstate', emitCurrentLocation);
}

/** Register the shell's view-mount callback. */
export function onSpaNavigate(callback: (target: NavigationTarget) => void): void {
  handler = callback;
}

/**
 * Navigate to ``href`` without a page reload.
 *
 * Returns ``false`` when the URL is not an internal view, so callers can fall
 * back to ``window.location.assign``.
 */
export function openHref(href: string): boolean {
  const url = new URL(href, window.location.href);
  if (url.origin !== window.location.origin) {
    return false;
  }

  const target = resolveTarget(url);
  if (!target) {
    return false;
  }

  const next = url.pathname + url.search + url.hash;
  const current = window.location.pathname
    + window.location.search
    + window.location.hash;
  if (next !== current) {
    window.history.pushState(null, '', next);
    emit(target);
  }
  return true;
}
