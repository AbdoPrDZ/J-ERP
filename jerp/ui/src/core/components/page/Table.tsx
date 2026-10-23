import * as React from 'react';

import { model } from '../../model';
import { formatValue, navigateTo } from '../../utils';
import { usePage } from './context';

export interface TableFieldProps {
  name: string;
  label?: string;
}

/** Declares a table column. Renders nothing on its own. */
export function TableField(_props: TableFieldProps) {
  return null;
}

/** Kept for compatibility; record details now open on their own page. */
export function TableRecordDetails({ children }: { children?: React.ReactNode }) {
  return <>{children}</>;
}

export function isTableField(node: React.ReactNode): node is React.ReactElement<TableFieldProps> {
  return React.isValidElement(node) && node.type === TableField;
}

export interface TableAction {
  label: string;
  /** Model API method to call (data action). */
  method?: string;
  /** Or a view type to open the record in (navigation action). */
  view?: string;
  key?: string;
  style?: 'primary' | 'default' | 'danger';
}

export interface TableProps {
  model: string;
  title?: string;
  emptyMessage?: string;
  onRowClick?: (record: Record<string, unknown>) => void;
  actions?: TableAction[];
  children?: React.ReactNode;
}

const ACTION_STYLES: Record<string, string> = {
  primary: 'bg-blue-600 text-white hover:bg-blue-700',
  danger: 'border border-red-200 text-red-600 hover:bg-red-50',
  default: 'border border-slate-300 text-slate-700 hover:bg-slate-50',
};

export function Table({
  model: modelName,
  emptyMessage = 'No records.',
  onRowClick,
  actions,
  children,
}: TableProps) {
  const page = usePage();
  const active = !page || page.view === 'list';

  const columns = React.Children.toArray(children).filter(isTableField);
  const fieldNames = columns.map((column) => column.props.name);

  const [records, setRecords] = React.useState<Record<string, unknown>[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState<string | null>(null);

  const columnKey = fieldNames.join(',');
  const load = React.useCallback(async () => {
    if (!active) {
      return;
    }
    setError(null);
    try {
      const data = await model(modelName).all({
        fields: columnKey ? columnKey.split(',') : undefined,
        limit: 100,
      });
      setRecords(data as Record<string, unknown>[]);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [active, modelName, columnKey]);

  React.useEffect(() => {
    void load();
  }, [load]);

  if (!active) {
    return null;
  }

  const canOpen = page ? page.open : true;
  const canDelete = page ? page.delete : true;

  // Clicking a row opens the record (there is no separate "Open" button).
  const rowClick =
    onRowClick ??
    (canOpen ? (record: Record<string, unknown>) => navigateTo({ view: 'form', id: record.id }) : undefined);

  const actionsOf = (record: Record<string, unknown>): TableAction[] => {
    const list: TableAction[] = [
      ...((record._actions as TableAction[] | undefined) ?? actions ?? []),
    ];
    if (canDelete) {
      list.push({ label: 'Delete', method: 'delete', key: 'id', style: 'danger' });
    }
    return list;
  };

  const run = async (action: TableAction, record: Record<string, unknown>) => {
    const key = action.key ?? 'id';
    if (action.view) {
      navigateTo({ view: action.view, id: record[key] });
      return;
    }
    if (!action.method) {
      return;
    }
    setBusy(String(record[key]));
    setError(null);
    try {
      await model(modelName).call(action.method, { [key]: record[key] });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const hasActions = records.some((record) => actionsOf(record).length > 0);

  return (
    <div className="space-y-4">
      {error ? (
        <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              {columns.map((column, index) => (
                <th key={index} className="px-4 py-2 font-medium">
                  {column.props.label ?? column.props.name}
                </th>
              ))}
              {hasActions ? <th className="px-4 py-2" /> : null}
            </tr>
          </thead>
          <tbody>
            {records.map((record, rowIndex) => (
              <tr
                key={String(record.id ?? rowIndex)}
                className={`border-b border-slate-100 last:border-0 ${
                  rowClick ? 'cursor-pointer hover:bg-slate-100' : ''
                }`}
              >
                {columns.map((column, columnIndex) => (
                  <td
                    key={columnIndex}
                    className="px-4 py-2 text-slate-700"
                    onClick={rowClick ? () => rowClick(record) : undefined}
                  >
                    {formatValue(record[column.props.name])}
                  </td>
                ))}
                {hasActions ? (
                  <td className="px-4 py-2 text-right">
                    <div className="flex justify-end gap-2">
                      {actionsOf(record).map((action) => (
                        <button
                          key={action.label}
                          type="button"
                          className={`rounded px-3 py-1 text-sm disabled:opacity-40 ${
                            ACTION_STYLES[action.style ?? 'default'] ?? ACTION_STYLES.default
                          }`}
                          disabled={busy !== null}
                          onClick={() => void run(action, record)}
                        >
                          {action.label}
                        </button>
                      ))}
                    </div>
                  </td>
                ) : null}
              </tr>
            ))}
            {records.length === 0 ? (
              <tr>
                <td
                  colSpan={Math.max(1, columns.length + (hasActions ? 1 : 0))}
                  className="px-4 py-6 text-center text-slate-400"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
