import * as React from 'react';

import { api } from './api';

export interface MenuItem {
  label: string;
  href?: string;
  img?: string;
  auth?: boolean;
  sequence?: number;
  description?: string;
  children?: MenuItem[];
}

interface MenuPayload {
  menus?: MenuItem[];
}

/** One shared request per page load; every consumer sees the same tree. */
let pending: Promise<MenuItem[]> | null = null;

export function loadMenus(): Promise<MenuItem[]> {
  if (!pending) {
    pending = api
      .getFresh<MenuPayload>('/menu')
      .then((payload) =>
        Array.isArray(payload?.menus) ? payload.menus : [],
      )
      .catch(() => []);
  }
  return pending;
}

/** Navigation entries for the active database, fetched from ``GET /api/menu``. */
export function useMenu(): MenuItem[] {
  const [menus, setMenus] = React.useState<MenuItem[]>([]);

  React.useEffect(() => {
    let cancelled = false;
    void loadMenus().then((value) => {
      if (!cancelled) {
        setMenus(value);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return menus;
}
