import { t } from '../../i18n';
import { RecordActions } from './actions';
import { formatValue } from '../../utils';
import type { StandardViewProps } from '../../types';

export function TableView({ view, records, onAction, busy }: StandardViewProps) {
  const columns = view.fields;
  const hasActions = records.some(
    (record) => (record._actions ?? view.actions ?? []).length > 0,
  );

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-brand-white text-left text-slate-500">
            {columns.map((column) => (
              <th key={column.name} className="px-4 py-2 font-medium">
                {column.label}
              </th>
            ))}
            {hasActions ? <th className="px-4 py-2" /> : null}
          </tr>
        </thead>
        <tbody>
          {records.map((record, index) => (
            <tr
              key={String(record.id ?? index)}
              className="border-b border-slate-100 last:border-0"
            >
              {columns.map((column) => (
                <td key={column.name} className="px-4 py-2 text-slate-700">
                  {formatValue(record[column.name])}
                </td>
              ))}
              {hasActions ? (
                <td className="px-4 py-2">
                  <RecordActions
                    actions={record._actions ?? view.actions}
                    record={record}
                    onAction={onAction}
                    busy={busy}
                  />
                </td>
              ) : null}
            </tr>
          ))}
          {records.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length + 1}
                className="px-4 py-6 text-center text-slate-400"
              >
                {t('app.no_records')}
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
