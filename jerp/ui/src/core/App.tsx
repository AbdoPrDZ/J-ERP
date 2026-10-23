import * as React from 'react';
import type { ComponentType } from 'react';

import { isLoggedIn, readJson } from './utils';
import { api } from './api';
import { model } from './model';
import type { ViewProps } from './types';

export interface AppProps {
  viewKey: string;
  context: Record<string, unknown>;
  view: ComponentType<ViewProps>;
}

interface MenuItem {
  label: string;
  href?: string;
  img?: string;
  auth?: boolean;
  sequence?: number;
  children?: MenuItem[];
}

interface PageMeta {
  auth?: boolean;
  header?: boolean;
  menu?: boolean;
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

function MenuEntry({ item }: { item: MenuItem }) {
  if (item.children && item.children.length > 0) {
    return (
      <div className="group relative">
        <button
          type="button"
          className="rounded px-3 py-1 text-slate-600 hover:bg-slate-100 hover:text-slate-900"
        >
          {item.label} ▾
        </button>
        <div className="absolute left-0 top-full z-20 hidden min-w-44 flex-col rounded-md border border-slate-200 bg-white py-1 shadow-lg group-hover:flex">
          {item.children.map((child) => (
            <MenuEntry key={child.label} item={child} />
          ))}
        </div>
      </div>
    );
  }
  return (
    <a
      href={item.href}
      className="block rounded px-3 py-1 text-slate-600 hover:bg-slate-100 hover:text-slate-900"
    >
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

/** A deterministic colour derived from the name (for the fallback avatar). */
function avatarColor(name: string): string {
  let hash = 0;
  for (let index = 0; index < name.length; index += 1) {
    hash = (hash * 31 + name.charCodeAt(index)) % 360;
  }
  return `hsl(${hash}, 60%, 45%)`;
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
        const users = await model('user').all<UserMenuUser>({
          domain: [['username', '=', userName]],
          limit: 1,
        });
        if (cancelled) {
          return;
        }
        const record = users[0] ?? null;
        setUser(record);
        if (record?.image) {
          const file = await model('file').find<{ path: string }>(record.image);
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
        className="flex items-center gap-2 rounded px-2 py-1 hover:bg-slate-100"
      >
        {path ? (
          <img
            src={`/__storage/${path}`}
            alt={userName}
            className="h-8 w-8 rounded-full object-cover"
          />
        ) : (
          <span
            className="flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium text-white"
            style={{ backgroundColor: avatarColor(userName) }}
          >
            {initial}
          </span>
        )}
        <span className="text-sm text-slate-700">{userName}</span>
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
  const menus = readJson<MenuItem[]>('__JERP_MENUS__', []);
  const pages = readJson<Record<string, PageMeta>>('__JERP_PAGES__', {});
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  const meta = pages[viewKey] ?? {};
  const showHeader = meta.header !== false;

  const userName = currentUsername();
  const roots = visibleMenus(menus, isLoggedIn());
  const current = new URL(window.location.href);
  const activeRoot = roots.find((item) => isActive(item, current)) ?? roots[0];
  const headerItems = activeRoot?.children ?? [];

  const logout = async () => {
    try {
      await api.post('/logout');
    } catch {
      // ignore
    }
    window.location.assign('/');
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {drawerOpen ? (
        <div className="fixed inset-0 z-40 flex">
          <div
            className="absolute inset-0 bg-slate-900/50"
            onClick={() => setDrawerOpen(false)}
          />
          <aside className="relative z-10 h-full w-64 overflow-y-auto bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <span className="text-lg font-semibold tracking-tight">J-ERP</span>
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                className="rounded px-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                ✕
              </button>
            </div>
            <nav className="flex flex-col gap-1 p-2">
              {roots.map((item) => (
                <a
                  key={item.label}
                  href={rootHref(item)}
                  onClick={() => setDrawerOpen(false)}
                  className={`rounded px-3 py-2 text-sm ${
                    item === activeRoot
                      ? 'bg-slate-100 font-medium text-slate-900'
                      : 'text-slate-600 hover:bg-slate-50'
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
        <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-slate-200 bg-white px-4 py-3">
          <button
            type="button"
            aria-label="Menu"
            onClick={() => setDrawerOpen(true)}
            className="rounded px-2 py-1 text-lg leading-none text-slate-600 hover:bg-slate-100"
          >
            ☰
          </button>
          <span className="text-lg font-semibold tracking-tight">J-ERP</span>
          {headerItems.length > 0 ? (
            <nav className="flex flex-wrap items-center gap-1 text-sm">
              {headerItems.map((item) => (
                <MenuEntry key={item.label} item={item} />
              ))}
            </nav>
          ) : null}
          {userName ? <UserMenu userName={userName} onLogout={() => void logout()} /> : null}
        </header>
      ) : null}

      <main className="mx-auto max-w-5xl p-6">
        <View context={context} />
      </main>
    </div>
  );
}
