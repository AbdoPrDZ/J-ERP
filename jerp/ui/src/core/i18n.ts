import * as React from 'react';

import { api } from './api';

export interface LocaleLanguage {
  code: string;
  name: string;
  is_default?: boolean;
}

export interface LocalePayload {
  lang?: string;
  dir?: 'ltr' | 'rtl' | string;
  messages?: Record<string, string>;
  fallback?: Record<string, string>;
  languages?: LocaleLanguage[];
}

let messages: Record<string, string> = {};
let fallbackMessages: Record<string, string> = {};
let language = 'en';
let direction: 'ltr' | 'rtl' = 'ltr';
let languages: LocaleLanguage[] = [];
let version = 0;
const listeners = new Set<() => void>();

function notify(): void {
  version += 1;
  for (const listener of listeners) {
    listener();
  }
}

/** Apply a catalog returned by ``GET /api/i18n``. */
export function setLocale(payload: LocalePayload): void {
  messages = payload.messages ?? {};
  fallbackMessages = payload.fallback ?? {};
  language = payload.lang ?? 'en';
  direction = payload.dir === 'rtl' ? 'rtl' : 'ltr';
  languages = payload.languages ?? [];

  if (typeof document !== 'undefined') {
    document.documentElement.lang = language;
    document.documentElement.dir = direction;
  }
  notify();
}

/** Fetch the active catalog before the first view mounts. */
export async function loadLocale(): Promise<void> {
  try {
    const payload = await api.getFresh<LocalePayload>('/i18n');
    setLocale(payload);
  } catch {
    setLocale({ lang: 'en', dir: 'ltr' });
  }
}

/** Translate a key, falling back to the default catalog, then the key itself. */
export function t(
  key: string,
  params?: Record<string, string | number>,
): string {
  let value = messages[key] || fallbackMessages[key] || key;
  if (params) {
    for (const [name, replacement] of Object.entries(params)) {
      value = value.split(`{${name}}`).join(String(replacement));
    }
  }
  return value;
}

/** Persist the selected language for the current user and reload the shell. */
export async function setLanguage(code: string): Promise<void> {
  await api.post('/lang', { code });
  window.location.reload();
}

export function useLocale(): {
  lang: string;
  dir: 'ltr' | 'rtl';
  languages: LocaleLanguage[];
  setLanguage: (code: string) => Promise<void>;
} {
  React.useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => version,
    () => version,
  );

  return { lang: language, dir: direction, languages, setLanguage };
}
