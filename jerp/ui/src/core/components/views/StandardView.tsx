import * as React from 'react';

import { api } from '../../api';
import { t } from '../../i18n';
import { viewRegistry } from './registry';
import type { ActionDescriptor, RecordType, ViewDescriptor } from '../../types';

/**
 * Renders any standard view: it reads the view descriptor from the page context
 * and dispatches to the component registered for its ``type`` (form/table/cards).
 */
export function StandardView({ context }: { context: Record<string, unknown> }) {
  const view = context.view as ViewDescriptor | undefined;
  const records = (context.records as RecordType[] | undefined) ?? [];
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  if (!view) {
    return (
      <p className="text-sm text-red-600">{t('app.missing_view_descriptor')}</p>
    );
  }

  const Component = viewRegistry.get(view.type);
  if (!Component) {
    return (
      <p className="text-sm text-red-600">
        {t('app.missing_view_component', { type: view.type })}
      </p>
    );
  }

  const onAction = async (action: ActionDescriptor, record: RecordType) => {
    if (busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const key = action.key ?? 'id';
      await api.post(action.endpoint, { [key]: record[key] });
      window.location.reload();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      {view.title ? (
        <h2 className="text-xl font-semibold">{view.title}</h2>
      ) : null}
      {error ? (
        <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}
      <Component view={view} records={records} onAction={onAction} busy={busy} />
    </div>
  );
}
