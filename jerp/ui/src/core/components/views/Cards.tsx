import { RecordActions } from './actions';
import { formatValue } from '../../utils';
import type { StandardViewProps } from '../../types';

export function CardsView({ view, records, onAction, busy }: StandardViewProps) {
  const [titleField, ...rest] = view.fields;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {records.map((record, index) => (
        <div
          key={String(record.id ?? index)}
          className="flex flex-col rounded-lg border border-slate-200 bg-white p-5"
        >
          <h3 className="font-medium text-brand-navy">
            {titleField ? formatValue(record[titleField.name]) : ''}
          </h3>
          <dl className="mt-2 flex-1 space-y-1 text-sm">
            {rest.map((field) => (
              <div key={field.name} className="flex gap-2">
                <dt className="shrink-0 text-slate-400">{field.label}</dt>
                <dd className="truncate text-slate-600">
                  {formatValue(record[field.name])}
                </dd>
              </div>
            ))}
          </dl>
          <div className="mt-4">
            <RecordActions
              actions={record._actions ?? view.actions}
              record={record}
              onAction={onAction}
              busy={busy}
            />
          </div>
        </div>
      ))}
      {records.length === 0 ? (
        <p className="text-sm text-slate-400">No records.</p>
      ) : null}
    </div>
  );
}
