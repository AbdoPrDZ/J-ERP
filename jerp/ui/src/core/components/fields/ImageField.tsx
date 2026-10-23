import * as React from 'react';

import { api } from '../../api';
import { model } from '../../model';
import { uploadFile } from '../../utils';
import type { FieldProps } from './registry';

interface Confirmed {
  id: number;
  name: string;
  path: string;
}

/** Like FileField, but shows an image preview (stored files are served at /file/…). */
export function ImageField({ value, onChange, readonly }: FieldProps) {
  const [name, setName] = React.useState<string | null>(null);
  const [path, setPath] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Load the existing file's metadata to show a preview.
  React.useEffect(() => {
    if (value === null || value === undefined || value === '') {
      setName(null);
      setPath(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const record = await model('file').find<{ name: string; path: string }>(
          value as number,
        );
        if (!cancelled && record) {
          setName(record.name);
          setPath(record.path);
        }
      } catch {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [value]);

  const pick = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const uploaded = await uploadFile(file);
      const confirmed = await api.post<Confirmed>('/upload/confirm', uploaded);
      setName(confirmed.name);
      setPath(confirmed.path);
      onChange(confirmed.id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-start gap-3">
      {path ? (
        <img
          src={`/__storage/${path}`}
          alt={name ?? ''}
          className="h-20 w-20 rounded border border-slate-200 object-cover"
        />
      ) : null}
      <div className="space-y-1">
        <input
          type="file"
          accept="image/*"
          disabled={readonly}
          onChange={pick}
          className="block w-full text-sm text-slate-600 file:mr-3 file:rounded file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm file:text-slate-700"
        />
        {busy ? <span className="block text-xs text-slate-500">Uploading…</span> : null}
        {name ? <span className="block text-xs text-slate-600">{name}</span> : null}
        {error ? <span className="block text-xs text-red-600">{error}</span> : null}
      </div>
    </div>
  );
}
