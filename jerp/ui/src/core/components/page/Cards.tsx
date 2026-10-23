import * as React from 'react';

import { model } from '../../model';
import { formatValue, navigateTo } from '../../utils';
import { isTableField } from './Table';
import { RecordContext, usePage } from './context';

export interface CardsProps {
  model: string;
  title?: string;
  emptyMessage?: string;
  onCardClick?: (record: Record<string, unknown>) => void;
  children?: React.ReactNode;
}

/** Cards over a model's records; fields come from ``TableField`` children. */
export function Cards({
  model: modelName,
  emptyMessage = 'No records.',
  onCardClick,
  children,
}: CardsProps) {
  const page = usePage();
  const active = !page || page.view === 'cards';

  const items = React.Children.toArray(children);
  const fields = items.filter(isTableField);
  const custom = items.filter((node) => !isTableField(node));

  const [records, setRecords] = React.useState<Record<string, unknown>[]>([]);
  const [error, setError] = React.useState<string | null>(null);

  const fieldKey = fields.map((field) => field.props.name).join(',');
  const load = React.useCallback(async () => {
    if (!active) {
      return;
    }
    setError(null);
    try {
      const data = await model(modelName).all({
        fields: fieldKey ? fieldKey.split(',') : undefined,
        limit: 100,
      });
      setRecords(data as Record<string, unknown>[]);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [active, modelName, fieldKey]);

  React.useEffect(() => {
    void load();
  }, [load]);

  if (!active) {
    return null;
  }

  const cardClick =
    onCardClick ??
    (page?.open ? (record: Record<string, unknown>) => navigateTo({ view: 'form', id: record.id }) : undefined);

  return (
    <div className="space-y-4">
      {error ? (
        <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {records.map((record, index) => (
          <RecordContext.Provider key={String(record.id ?? index)} value={record}>
            <div
              onClick={cardClick ? () => cardClick(record) : undefined}
              className={`rounded-lg border border-slate-200 bg-white p-5 ${
                cardClick ? 'cursor-pointer hover:border-blue-300 hover:bg-blue-50' : ''
              }`}
            >
              {custom.length > 0 ? <div className="mb-2">{custom}</div> : null}
              {fields.length > 0 ? (
                <>
                  <h3 className="font-medium text-slate-800">
                    {formatValue(record[fields[0].props.name])}
                  </h3>
                  <dl className="mt-2 space-y-1 text-sm">
                    {fields.slice(1).map((field, fieldIndex) => (
                      <div key={fieldIndex} className="flex gap-2">
                        <dt className="shrink-0 text-slate-400">
                          {field.props.label ?? field.props.name}
                        </dt>
                        <dd className="truncate text-slate-600">
                          {formatValue(record[field.props.name])}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </>
              ) : null}
            </div>
          </RecordContext.Provider>
        ))}
        {records.length === 0 ? (
          <p className="text-sm text-slate-400">{emptyMessage}</p>
        ) : null}
      </div>
    </div>
  );
}
