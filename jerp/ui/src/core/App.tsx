import * as React from 'react';
import type { ComponentType } from 'react';

import { isLoggedIn, readJson } from './utils';
import { api } from './api';
import { model } from './model';
import { MenuSearch } from './components/MenuSearch';
import { useLoading } from './loading';
import { useMenu, type MenuItem } from './menu';
import { openHref } from './navigation';
import type { ViewProps } from './types';

export interface AppProps {
  viewKey: string;
  context: Record<string, unknown>;
  view: ComponentType<ViewProps>;
}

interface PageMeta {
  auth?: boolean;
  header?: boolean;
  menu?: boolean;
  drawer?: boolean;
}

/** Drop auth-required items when logged out; drop groups left empty. */
function visibleMenus(items: MenuItem[], loggedIn: boolean): MenuItem[] {
  const result: MenuItem[] = [];
  for (const item of items) {
    if (item.children && item.children.length > 0) {
      const children = visibleMenus(item.children, loggedIn);
      if (children.length > 0) {
        result.push({ ...item, children });
      }
    } else if (item.auth === false || loggedIn) {
      result.push(item);
    }
  }
  return result;
}

function sameTarget(href: string | undefined, current: URL): boolean {
  if (!href) {
    return false;
  }
  const target = new URL(href, current.origin);
  const a = target.searchParams.get('name');
  const b = current.searchParams.get('name');
  if (a || b) {
    return a === b;
  }
  return target.pathname === current.pathname;
}

function isActive(item: MenuItem, current: URL): boolean {
  if (sameTarget(item.href, current)) {
    return true;
  }
  return (item.children ?? []).some((child) => isActive(child, current));
}

function rootHref(item: MenuItem): string | undefined {
  return item.href ?? item.children?.[0]?.href;
}

function MenuEntry({
  item,
  surface = 'dark',
  active = false,
}: {
  item: MenuItem;
  surface?: 'dark' | 'light';
  active?: boolean;
}) {
  const itemClass =
    surface === 'dark'
      ? `block rounded px-3 py-1 transition-colors duration-150 ${
          active
            ? 'bg-white/10 font-medium text-brand-cyan'
            : 'text-white/80 hover:bg-white/10 hover:text-white'
        }`
      : `block rounded px-3 py-1 transition-colors duration-150 ${
          active
            ? 'bg-brand-white font-medium text-brand-blue'
            : 'text-slate-700 hover:bg-slate-100 hover:text-brand-navy'
        }`;
  const panelClass =
    surface === 'dark'
      ? 'pointer-events-none invisible absolute left-0 top-full z-20 flex min-w-44 -translate-y-1 flex-col rounded-md border border-white/10 bg-brand-navy-soft py-1 opacity-0 shadow-lg transition-all duration-150 group-hover:visible group-hover:pointer-events-auto group-hover:translate-y-0 group-hover:opacity-100'
      : 'pointer-events-none invisible absolute left-0 top-full z-20 flex min-w-44 -translate-y-1 flex-col rounded-md border border-slate-200 bg-white py-1 opacity-0 shadow-lg transition-all duration-150 group-hover:visible group-hover:pointer-events-auto group-hover:translate-y-0 group-hover:opacity-100';

  if (item.children && item.children.length > 0) {
    return (
      <div className="group relative">
        <button type="button" className={itemClass}>
          {item.label}{' '}
          <span className="inline-block text-[10px] transition-transform duration-150 group-hover:rotate-180">
            ▾
          </span>
        </button>
        <div className={panelClass}>
          {item.children.map((child) => (
            <MenuEntry key={child.label} item={child} surface={surface} />
          ))}
        </div>
      </div>
    );
  }
  return (
    <a href={item.href} className={itemClass}>
      {item.label}
    </a>
  );
}

interface UserMenuUser {
  id: number;
  name: string;
  image?: number | null;
}

function currentUsername(): string {
  const match = document.cookie.match(/(?:^|;\s*)jerp_user=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

function UserMenu({ userName, onLogout }: { userName: string; onLogout: () => void }) {
  const [user, setUser] = React.useState<UserMenuUser | null>(null);
  const [path, setPath] = React.useState<string | null>(null);
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    if (!userName) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const users = await model('sys.user').all<UserMenuUser>({
          domain: [['username', '=', userName]],
          limit: 1,
        });
        if (cancelled) {
          return;
        }
        const record = users[0] ?? null;
        setUser(record);
        if (record?.image) {
          const file = await model('sys.file').find<{ path: string }>(record.image);
          if (!cancelled && file) {
            setPath(file.path);
          }
        }
      } catch {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userName]);

  const initial = userName.charAt(0).toUpperCase();

  return (
    <div className="relative ml-auto">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-2 rounded px-2 py-0.5 hover:bg-white/10"
      >
        {path ? (
          <img
            src={`/__storage/${path}`}
            alt={userName}
            className="h-7 w-7 rounded-full object-cover"
          />
        ) : (
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-cyan text-sm font-semibold text-brand-navy">
            {initial}
          </span>
        )}
        <span className="text-sm text-white/90">{userName}</span>
      </button>

      {open ? (
        <div className="absolute right-0 top-full z-30 mt-1 min-w-44 rounded-md border border-slate-200 bg-white py-1 shadow-lg">
          <a
            href="/view?name=core.profile"
            onClick={() => setOpen(false)}
            className="block px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
          >
            Profile
          </a>
          <button
            type="button"
            onClick={onLogout}
            className="block w-full px-3 py-1.5 text-left text-sm text-red-600 hover:bg-red-50"
          >
            Logout
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function App({ viewKey, context, view: View }: AppProps) {
  const menus = useMenu();
  const pages = readJson<Record<string, PageMeta>>('__JERP_PAGES__', {});
  const loading = useLoading();
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerMounted, setDrawerMounted] = React.useState(false);
  const [searchFocus, setSearchFocus] = React.useState(0);
  const contentRef = React.useRef<HTMLDivElement>(null);
  const drawerTimer = React.useRef<number | null>(null);
  const drawerWanted = React.useRef(false);

  const openDrawer = React.useCallback(() => {
    drawerWanted.current = true;
    if (drawerTimer.current !== null) {
      window.clearTimeout(drawerTimer.current);
      drawerTimer.current = null;
    }
    setDrawerMounted(true);
    window.requestAnimationFrame(() => {
      if (drawerWanted.current) {
        setDrawerOpen(true);
      }
    });
  }, []);

  const closeDrawer = React.useCallback(() => {
    drawerWanted.current = false;
    setDrawerOpen(false);
    if (drawerTimer.current !== null) {
      window.clearTimeout(drawerTimer.current);
    }
    drawerTimer.current = window.setTimeout(() => {
      setDrawerMounted(false);
      drawerTimer.current = null;
    }, 300);
  }, []);

  React.useEffect(() => () => {
    if (drawerTimer.current !== null) {
      window.clearTimeout(drawerTimer.current);
    }
  }, []);

  const viewInstanceKey = `${viewKey}:${JSON.stringify(context)}`;

  React.useEffect(() => {
    contentRef.current?.scrollTo({ top: 0 });
  }, [viewInstanceKey]);

  const meta = pages[viewKey] ?? {};
  const showHeader = meta.header !== false;
  const showDrawer = meta.drawer !== false;

  React.useEffect(() => {
    if (!showDrawer) {
      drawerWanted.current = false;
      if (drawerTimer.current !== null) {
        window.clearTimeout(drawerTimer.current);
        drawerTimer.current = null;
      }
      setDrawerOpen(false);
      setDrawerMounted(false);
    }
  }, [showDrawer]);

  React.useEffect(() => {
    closeDrawer();
  }, [viewInstanceKey, closeDrawer]);

  const userName = currentUsername();
  const roots = React.useMemo(
    () => visibleMenus(menus, isLoggedIn()),
    [menus],
  );
  const current = new URL(window.location.href);
  const activeRoot = roots.find((item) => isActive(item, current)) ?? roots[0];
  const headerItems = activeRoot?.children ?? [];

  React.useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && drawerOpen) {
        closeDrawer();
        return;
      }
      if (!(event.ctrlKey || event.metaKey)) {
        return;
      }
      if (event.key.toLowerCase() !== 'k') {
        return;
      }
      if (!showDrawer || !isLoggedIn()) {
        return;
      }
      event.preventDefault();
      openDrawer();
      setSearchFocus((value) => value + 1);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [showDrawer, drawerOpen, openDrawer, closeDrawer]);

  const logout = async () => {
    try {
      await api.post('/logout');
    } catch {
      // ignore
    }
    window.location.assign('/');
  };

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-brand-white text-brand-navy">
      <div
        className={`pointer-events-none fixed inset-x-0 top-0 z-50 h-0.5 overflow-hidden bg-brand-cyan/15 transition-opacity duration-200 ${
          loading ? 'opacity-100' : 'opacity-0'
        }`}
        aria-hidden="true"
      >
        <div
          className={`h-full w-1/3 bg-gradient-to-r from-transparent via-brand-cyan to-transparent ${
            loading ? 'jerp-loading-bar' : ''
          }`}
        />
      </div>

      {showDrawer && drawerMounted ? (
        <div
          className={`fixed inset-0 z-40 flex transition-opacity duration-300 ${
            drawerOpen
              ? 'pointer-events-auto opacity-100'
              : 'pointer-events-none opacity-0'
          }`}
          aria-hidden={!drawerOpen}
        >
          <div
            className="absolute inset-0 bg-brand-navy/60 backdrop-blur-[1px]"
            onClick={closeDrawer}
          />
          <aside
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
            className={`relative z-10 h-full w-64 overflow-y-auto bg-gradient-to-b from-brand-navy to-brand-navy-soft text-white shadow-xl transition-transform duration-300 ease-out will-change-transform ${
              drawerOpen ? 'translate-x-0' : '-translate-x-full'
            }`}
          >
            <div className="flex items-center justify-between border-b border-white/10 px-4 py-2">
              <span className="text-base font-semibold tracking-tight">J-ERP</span>
              <button
                type="button"
                onClick={closeDrawer}
                className="rounded px-2 text-white/60 transition-all duration-150 hover:scale-110 hover:bg-white/10 hover:text-white active:scale-95"
              >
                ✕
              </button>
            </div>
            <div className="border-b border-white/10 p-2">
              <MenuSearch
                menus={roots}
                focusKey={searchFocus}
                onClose={closeDrawer}
                onNavigate={(href) => {
                  closeDrawer();
                  if (!openHref(href)) {
                    window.location.assign(href);
                  }
                }}
              />
            </div>
            <nav className="flex flex-col gap-1 p-2">
              {roots.map((item, index) => (
                <a
                  key={item.label}
                  href={rootHref(item)}
                  onClick={closeDrawer}
                  style={{ animationDelay: `${index * 30}ms` }}
                  className={`jerp-drawer-item rounded px-3 py-1.5 text-sm transition-colors duration-150 ${
                    item === activeRoot
                      ? 'border-l-2 border-brand-cyan bg-brand-blue font-medium text-white'
                      : 'text-white/70 hover:bg-white/10 hover:text-white'
                  }`}
                >
                  {item.label}
                </a>
              ))}
            </nav>
          </aside>
        </div>
      ) : null}

      {showHeader ? (
        <header
          className="sticky top-0 z-30 flex flex-none flex-wrap items-center gap-x-3 gap-y-1.5 border-b-2 border-brand-cyan bg-gradient-to-r from-brand-navy via-brand-navy-soft to-brand-blue px-4 py-1.5 text-white shadow-md"
        >
          {showDrawer ? (
            <button
              type="button"
              aria-label="Menu"
              onClick={openDrawer}
              className="rounded px-2 py-0.5 text-base leading-none text-white/80 transition-all duration-150 hover:scale-110 hover:bg-white/10 hover:text-white active:scale-95"
            >
              ☰
            </button>
          ) : null}
          <span className="text-base font-semibold tracking-tight">J-ERP</span>
          <span
            aria-label={loading ? 'Loading' : undefined}
            aria-hidden={!loading}
            role={loading ? 'status' : undefined}
            className={`h-3.5 w-3.5 rounded-full border-2 border-white/25 border-t-brand-cyan transition-opacity duration-200 ${
              loading ? 'animate-spin opacity-100' : 'opacity-0'
            }`}
          />
          {headerItems.length > 0 ? (
            <nav className="flex flex-wrap items-center gap-1 text-sm">
              {headerItems.map((item) => (
                <MenuEntry
                  key={item.label}
                  item={item}
                  active={isActive(item, current)}
                />
              ))}
            </nav>
          ) : null}
          {userName ? <UserMenu userName={userName} onLogout={() => void logout()} /> : null}
        </header>
      ) : null}

      <main className="min-h-0 flex-1 overflow-hidden">
        <div
          ref={contentRef}
          className="flex h-full min-h-0 w-full flex-col overflow-y-auto px-4 py-3"
        >
          <div
            key={viewInstanceKey}
            className="jerp-view-enter flex min-h-0 flex-1 flex-col"
          >
            <View context={context} />
          </div>
        </div>
      </main>
    </div>
  );
}
