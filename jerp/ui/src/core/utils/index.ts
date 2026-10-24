import { utilsRegistry, type UtilFn } from './registry';
import { openHref } from '../navigation';

export { utilsRegistry } from './registry';
export type { UtilFn } from './registry';

/** Parse a JSON payload injected into the shell by the server. */
export function readJson<T>(id: string, fallback: T): T {
  const element = document.getElementById(id);
  if (!element || !element.textContent) {
    return fallback;
  }
  try {
    return JSON.parse(element.textContent) as T;
  } catch {
    return fallback;
  }
}

/** Format a record value for display. */
export function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '—';
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }
  return String(value);
}

/** Whether the current session is logged in (based on the ``jerp_user`` cookie). */
export function isLoggedIn(): boolean {
  return document.cookie
    .split(';')
    .some((cookie) => cookie.trim().startsWith('jerp_user='));
}

export interface UploadResult {
  token: string;
  name: string;
  mimetype: string;
  checksum: string;
  size: number;
}

/** Upload a file into the server's tmp area; returns a token to confirm. */
export async function uploadFile(file: File): Promise<UploadResult> {
  const response = await fetch(`/api/upload?name=${encodeURIComponent(file.name)}`, {
    method: 'POST',
    body: file,
    headers: { 'Content-Type': file.type || 'application/octet-stream' },
    credentials: 'same-origin',
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error((data && data.message) || response.statusText);
  }
  return data as UploadResult;
}

/** Navigate within the app, updating query params (keeps the path). */
export function navigateTo(params: Record<string, unknown>): void {
  const url = new URL(window.location.href);
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') {
      url.searchParams.delete(key);
    } else {
      url.searchParams.set(key, String(value));
    }
  }
  const query = url.searchParams.toString();
  const href = url.pathname + (query ? `?${query}` : '');
  if (!openHref(href)) {
    window.location.assign(href);
  }
}

/** Register the built-in J-ERP utilities. */
export function registerBuiltinUtils(): void {
  utilsRegistry.register('readJson', readJson as UtilFn);
  utilsRegistry.register('format', formatValue as UtilFn);
  utilsRegistry.register('isLoggedIn', isLoggedIn as UtilFn);
  utilsRegistry.register('upload', uploadFile as unknown as UtilFn);
  utilsRegistry.register('navigate', navigateTo as unknown as UtilFn);
}
