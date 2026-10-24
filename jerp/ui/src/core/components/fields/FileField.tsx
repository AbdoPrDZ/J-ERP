import * as React from 'react';

import { api } from '../../api';
import { t } from '../../i18n';
import { uploadFile } from '../../utils';
import type { FieldProps } from './registry';

interface Confirmed {
  id: number;
  name: string;
}

export function FileField({ value, onChange, readonly }: FieldProps) {
  const [name, setName] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

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
      onChange(confirmed.id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-1">
      <input
        type="file"
        disabled={readonly}
        onChange={pick}
        className="block w-full text-sm text-slate-600 file:mr-3 file:rounded file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm file:text-slate-700"
      />
      {busy ? (
        <span className="block text-xs text-slate-500">
          {t('app.uploading')}
        </span>
      ) : null}
      {name ? (
        <span className="block text-xs text-slate-600">{name}</span>
      ) : value ? (
        <span className="block text-xs text-slate-600">file #{String(value)}</span>
      ) : null}
      {error ? <span className="block text-xs text-red-600">{error}</span> : null}
    </div>
  );
}
