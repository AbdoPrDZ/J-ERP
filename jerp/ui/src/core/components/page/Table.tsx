import * as React from 'react';

import { model, type DataClient } from '../../model';
import { formatValue, navigateTo } from '../../utils';
import { fieldRegistry } from '../fields/registry';
import { Pagination, PAGE_SIZES } from './Pagination';
import { FormTabContext, RecordContext, usePage } from './context';
import { autoModelFields, useModelFields, useRelationLabels } from './useModelFields';

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

export interface TableInlineEdit {
  mode: 'create' | 'edit';
  editingId?: number | string | null;
  focusField?: string | null;
  values: Record<string, unknown>;
  errors: Record<string, string>;
  editableFields: string[];
  saving?: boolean;
  onChange: (name: string, value: unknown) => void;
  onSave: () => void;
  onCancel: () => void;
}

export interface TableProps {
  model: string;
  title?: string;
  emptyMessage?: string;
  domain?: unknown[];
  client?: DataClient;
  inlineEdit?: TableInlineEdit;
  refreshKey?: number;
  onDataChanged?: () => void;
  onRowClick?: (record: Record<string, unknown>) => void;
  onCellClick?: (record: Record<string, unknown>, field: string) => void;
  actions?: TableAction[];
  selectable?: boolean;
  allowDelete?: boolean;
  selectionActions?: (ids: string[]) => React.ReactNode;
  children?: React.ReactNode;
}

const ACTION_STYLES: Record<string, string> = {
  primary: 'bg-brand-blue text-white hover:bg-brand-blue-dark',
  danger: 'border border-red-200 text-red-600 hover:bg-red-50',
  default: 'border border-slate-300 text-slate-700 hover:border-brand-cyan hover:bg-brand-cyan/5',
};

function SelectionCheckbox({
  checked,
  indeterminate = false,
  onChange,
  label,
}: {
  checked: boolean;
  indeterminate?: boolean;
  onChange: React.ChangeEventHandler<HTMLInputElement>;
  label: string;
}) {
  const ref = React.useRef<HTMLInputElement | null>(null);

  React.useEffect(() => {
    if (ref.current) {
      ref.current.indeterminate = indeterminate;
    }
  }, [indeterminate]);

  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={onChange}
      aria-label={label}
      className="h-4 w-4 cursor-pointer rounded border-slate-300 text-brand-blue focus:ring-brand-cyan/50"
    />
  );
}

export function Table({
  model: modelName,
  emptyMessage = 'No records.',
  domain,
  client,
  inlineEdit,
  refreshKey = 0,
  onDataChanged,
  onRowClick,
  onCellClick,
  actions,
  selectable: selectableProp,
  allowDelete,
  selectionActions,
  children,
}: TableProps) {
  const page = usePage();
  const inFormTab = React.useContext(FormTabContext);
  const record = React.useContext(RecordContext);
  const active = inFormTab || !page || page.view === 'list';
  const recordId = record?.id;
  const domainKey = JSON.stringify(domain ?? null);
  const resolvedDomain = React.useMemo(() => {
    if (!domain) {
      return undefined;
    }
    return domain.map((leaf) => {
      if (!Array.isArray(leaf)) {
        return leaf;
      }
      return leaf.map((part, index) =>
        index === 2 && part === 'id' ? recordId : part,
      );
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domainKey, recordId]);

  const columns = React.Children.toArray(children).filter(isTableField);
  const schema = useModelFields(modelName);
  const autoEnabled = page?.autoFields ?? true;
  const autoFields = React.useMemo(
    () =>
      autoEnabled
        ? autoModelFields(
            schema,
            new Set(columns.map((column) => column.props.name)),
          )
        : [],
    [autoEnabled, schema, columns],
  );

  const columnSpecs = [
    ...columns.map((column) => {
      const descriptor = schema.find((field) => field.name === column.props.name);
      return {
        name: column.props.name,
        label: column.props.label ?? descriptor?.label ?? column.props.name,
        help: descriptor?.help ?? null,
        relation: descriptor?.relation ?? null,
        selection: descriptor?.selection ?? null,
        descriptor,
        ttype: descriptor?.ttype ?? 'char',
      };
    }),
    ...autoFields.map((field) => ({
      name: field.name,
      label: field.label ?? field.name,
      help: field.help ?? null,
      relation: field.relation ?? null,
      selection: field.selection ?? null,
      descriptor: field,
      ttype: field.ttype,
    })),
  ];
  const fieldNames = columnSpecs.map((column) => column.name);
  const relationLabels = useRelationLabels(schema);

  const displayValue = (
    column: (typeof columnSpecs)[number],
    record: Record<string, unknown>,
  ): string => {
    const raw = record[column.name];
    if (column.relation) {
      return (
        relationLabels[column.relation]?.[String(raw)] ?? formatValue(raw)
      );
    }
    if (column.selection) {
      const option = column.selection.find(
        ([key]) => String(key) === String(raw),
      );
      if (option) {
        return option[1];
      }
    }
    return formatValue(raw);
  };

  const [records, setRecords] = React.useState<Record<string, unknown>[]>([]);
  const [total, setTotal] = React.useState(0);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [pageNumber, setPageNumber] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(PAGE_SIZES[0]);
  const [sort, setSort] = React.useState<{
    field: string;
    direction: 'asc' | 'desc';
  } | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = React.useState(false);
  const loadId = React.useRef(0);
  const tableRef = React.useRef<HTMLTableElement | null>(null);

  const columnKey = fieldNames.join(',');
  const order = sort ? `${sort.field} ${sort.direction}` : undefined;

  // The model API applies ORDER BY / LIMIT / OFFSET, so every sort or page
  // change is a fresh server-side request.
  const load = React.useCallback(async () => {
    if (!active) {
      return;
    }
    const requestId = ++loadId.current;
    const source = client ?? model(modelName);
    setLoading(true);
    setError(null);
    try {
      const [data, count] = await Promise.all([
        source.all<Record<string, unknown>>({
          domain: resolvedDomain,
          fields: columnKey ? columnKey.split(',') : undefined,
          order,
          limit: pageSize,
          offset: (pageNumber - 1) * pageSize,
        }),
        source.count(resolvedDomain),
      ]);
      if (requestId !== loadId.current) {
        return;
      }
      setRecords(data);
      setTotal(count);
    } catch (err) {
      if (requestId === loadId.current) {
        setError((err as Error).message);
      }
    } finally {
      if (requestId === loadId.current) {
        setLoading(false);
      }
    }
  }, [active, client, modelName, columnKey, order, pageSize, pageNumber, resolvedDomain, refreshKey]);

  React.useEffect(() => {
    void load();
  }, [load]);

  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  React.useEffect(() => {
    if (pageNumber > pageCount) {
      setPageNumber(pageCount);
    }
  }, [pageNumber, pageCount]);

  React.useEffect(() => {
    const field = inlineEdit?.focusField;
    if (!field || !inlineEdit) {
      return;
    }
    const cell = tableRef.current?.querySelector(
      `[data-field="${field}"]`,
    );
    const input = cell?.querySelector(
      'input, select, textarea',
    ) as HTMLElement | null;
    input?.focus();
  }, [
    inlineEdit?.mode,
    inlineEdit?.editingId,
    inlineEdit?.focusField,
    records,
  ]);

  const changePageSize = (value: number) => {
    setPageSize(value);
    setPageNumber(1);
  };

  const toggleSort = (field: string) => {
    setPageNumber(1);
    setSort((current) => {
      if (!current || current.field !== field) {
        return { field, direction: 'asc' };
      }
      if (current.direction === 'asc') {
        return { field, direction: 'desc' };
      }
      return null;
    });
  };

  if (!active) {
    return null;
  }

  const canOpen = page ? page.open : true;
  const canDelete = allowDelete ?? (page ? page.delete : true);
  const selectable = selectableProp ?? canDelete;

  // Clicking a row opens the record (there is no separate "Open" button).
  const rowClick =
    onRowClick ??
    (!inFormTab && canOpen
      ? (record: Record<string, unknown>) =>
          navigateTo({ view: 'form', id: record.id })
      : undefined);

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
      await (client ?? model(modelName)).call(action.method, { [key]: record[key] });
      if (action.method === 'delete') {
        setSelected((current) => {
          const next = new Set(current);
          next.delete(String(record[key]));
          return next;
        });
      }
      await load();
      onDataChanged?.();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const pageIds = records.map((record) => String(record.id));
  const allPageSelected =
    pageIds.length > 0 && pageIds.every((id) => selected.has(id));
  const somePageSelected = pageIds.some((id) => selected.has(id));

  const toggleRecord = (id: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const togglePage = () => {
    setSelected((current) => {
      const next = new Set(current);
      if (allPageSelected) {
        pageIds.forEach((id) => next.delete(id));
      } else {
        pageIds.forEach((id) => next.add(id));
      }
      return next;
    });
  };

  const clearSelection = () => setSelected(new Set());

  const deleteSelected = async () => {
    if (!canDelete || selected.size === 0 || bulkBusy) {
      return;
    }
    const ids = Array.from(selected);
    const noun = ids.length === 1 ? 'record' : 'records';
    if (!window.confirm(`Delete ${ids.length} selected ${noun}?`)) {
      return;
    }
    setBulkBusy(true);
    setError(null);
    try {
      await (client ?? model(modelName)).deleteMany(ids);
      setSelected(new Set());
      await load();
      onDataChanged?.();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBulkBusy(false);
    }
  };

  const hasActions =
    Boolean(inlineEdit) ||
    canDelete ||
    records.some((record) => actionsOf(record).length > 0);

  const renderEditableRow = (
    record: Record<string, unknown> | null,
    key: React.Key,
  ) => {
    if (!inlineEdit) {
      return null;
    }
    const row = { ...(record ?? {}), ...inlineEdit.values };
    return (
      <tr key={key} className="border-b border-slate-100 bg-brand-cyan/5">
        {selectable ? <td className="w-10 px-3 py-2" /> : null}
        {columnSpecs.map((column, index) => {
          const descriptor = column.descriptor ?? {
            name: column.name,
            label: column.label,
            ttype: column.ttype,
          };
          const Widget = fieldRegistry.get(column.ttype) ?? fieldRegistry.get('char');
          const editable = inlineEdit.editableFields.includes(column.name);
          return (
            <td
              key={index}
              className="px-2 py-1 align-top text-slate-700"
              data-field={editable ? column.name : undefined}
            >
              {editable && Widget ? (
                <>
                  <Widget
                    field={descriptor}
                    value={row[column.name]}
                    readonly={false}
                    model={modelName}
                    recordId={inlineEdit.editingId ?? null}
                    onChange={(value) => inlineEdit.onChange(column.name, value)}
                  />
                  {inlineEdit.errors[column.name] ? (
                    <p className="mt-1 text-xs text-red-600">
                      {inlineEdit.errors[column.name]}
                    </p>
                  ) : null}
                </>
              ) : (
                <span className="block px-2 py-1">
                  {displayValue(column, row)}
                </span>
              )}
            </td>
          );
        })}
        {hasActions ? (
          <td className="px-2 py-1 text-right">
            <div className="flex justify-end gap-1">
              <button
                type="button"
                className="rounded bg-brand-blue px-2 py-1 text-xs font-medium text-white hover:bg-brand-blue-dark disabled:opacity-40"
                disabled={inlineEdit.saving}
                onClick={inlineEdit.onSave}
              >
                {inlineEdit.saving ? 'Saving…' : 'Save'}
              </button>
              <button
                type="button"
                className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:border-brand-cyan hover:bg-brand-cyan/5 disabled:opacity-40"
                disabled={inlineEdit.saving}
                onClick={inlineEdit.onCancel}
              >
                Cancel
              </button>
            </div>
          </td>
        ) : null}
      </tr>
    );
  };

  return (
    <div
      className={`flex flex-col gap-4 ${
        inFormTab ? '' : 'h-full min-h-0'
      }`}
    >
      {error ? (
        <div className="flex-none rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {selectable && selected.size > 0 ? (
        <div className="flex flex-none flex-wrap items-center justify-between gap-2 rounded-lg border border-brand-cyan/40 bg-brand-cyan/5 px-3 py-2 text-sm">
          <span className="font-medium text-brand-navy">
            {selected.size} selected
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="rounded border border-slate-300 px-3 py-1 text-slate-700 hover:border-brand-cyan hover:bg-brand-cyan/5 disabled:opacity-40"
              disabled={bulkBusy}
              onClick={clearSelection}
            >
              Clear
            </button>
            {selectionActions ? selectionActions(Array.from(selected)) : null}
            {canDelete ? (
              <button
                type="button"
                className="rounded bg-red-600 px-3 py-1 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-40"
                disabled={bulkBusy}
                onClick={() => void deleteSelected()}
              >
                {bulkBusy ? 'Deleting…' : 'Delete'}
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      <div
        className={`rounded-lg border border-slate-200 bg-white transition-opacity ${
          inFormTab ? 'overflow-x-auto' : 'min-h-0 flex-1 overflow-auto'
        } ${loading ? 'opacity-60' : ''}`}
        aria-busy={loading}
      >
        <table ref={tableRef} className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500">
              {selectable ? (
                <th className="sticky top-0 z-10 w-10 border-b border-slate-200 bg-brand-white px-3 py-2">
                  <SelectionCheckbox
                    checked={allPageSelected}
                    indeterminate={!allPageSelected && somePageSelected}
                    onChange={togglePage}
                    label="Select all rows on this page"
                  />
                </th>
              ) : null}
              {columnSpecs.map((column, index) => {
                const activeSort =
                  sort?.field === column.name ? sort : null;
                const alignRight = index >= columnSpecs.length / 2;
                return (
                  <th
                    key={index}
                    aria-sort={
                      activeSort
                        ? activeSort.direction === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : 'none'
                    }
                    className="sticky top-0 z-10 border-b border-slate-200 bg-brand-white p-0 font-medium"
                  >
                    <button
                      type="button"
                      onClick={() => toggleSort(column.name)}
                      aria-label={`Sort by ${column.label}${
                        column.help ? `: ${column.help}` : ''
                      }`}
                      className="group/col relative flex w-full items-center gap-1.5 px-4 py-2 text-left font-medium text-slate-500 hover:bg-brand-cyan/5 hover:text-brand-navy focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-cyan/60"
                    >
                      <span className="min-w-0 truncate">{column.label}</span>
                      <span
                        className={`text-[10px] ${
                          activeSort ? 'text-brand-blue' : 'text-slate-300'
                        }`}
                      >
                        {activeSort
                          ? activeSort.direction === 'asc'
                            ? '▲'
                            : '▼'
                          : '↕'}
                      </span>
                      {column.help ? (
                        <span
                          role="tooltip"
                          aria-hidden="true"
                          className={`pointer-events-none invisible absolute top-full z-50 mt-1 w-64 rounded-md bg-brand-navy px-3 py-2 text-left text-xs font-normal leading-snug text-white opacity-0 shadow-lg transition-opacity group-hover/col:visible group-hover/col:opacity-100 group-focus/col:visible group-focus/col:opacity-100 ${
                            alignRight ? 'right-0' : 'left-0'
                          }`}
                        >
                          {column.help}
                        </span>
                      ) : null}
                    </button>
                  </th>
                );
              })}
              {hasActions ? (
                <th
                  className="sticky top-0 z-10 border-b border-slate-200 bg-brand-white px-4 py-2"
                />
              ) : null}
            </tr>
          </thead>
          <tbody>
            {inlineEdit?.mode === 'create'
              ? renderEditableRow(null, 'new')
              : null}
            {records.map((record, rowIndex) => {
              if (
                inlineEdit?.mode === 'edit' &&
                String(record.id) === String(inlineEdit.editingId)
              ) {
                return renderEditableRow(
                  record,
                  String(record.id ?? `edit-${rowIndex}`),
                );
              }
              return (
                <tr
                  key={String(record.id ?? rowIndex)}
                  className={`border-b border-slate-100 last:border-0 ${
                    rowClick || onCellClick
                      ? 'cursor-pointer hover:bg-brand-cyan/5'
                      : ''
                  } ${selected.has(String(record.id)) ? 'bg-brand-cyan/5' : ''}`}
                >
                  {selectable ? (
                    <td
                      className="w-10 px-3 py-2"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <SelectionCheckbox
                        checked={selected.has(String(record.id))}
                        onChange={() => toggleRecord(String(record.id))}
                        label={`Select ${String(record._label ?? record.id ?? '')}`}
                      />
                    </td>
                  ) : null}
                  {columnSpecs.map((column, columnIndex) => (
                    <td
                      key={columnIndex}
                      className="px-4 py-2 text-slate-700"
                      onClick={
                        onCellClick
                          ? () => onCellClick(record, column.name)
                          : rowClick
                            ? () => rowClick(record)
                            : undefined
                      }
                    >
                      {displayValue(column, record)}
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
              );
            })}
            {records.length === 0 && inlineEdit?.mode !== 'create' ? (
              <tr>
                <td
                  colSpan={Math.max(
                    1,
                    columnSpecs.length +
                      (hasActions ? 1 : 0) +
                      (selectable ? 1 : 0),
                  )}
                  className="px-4 py-6 text-center text-slate-400"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <Pagination
        page={pageNumber}
        pageSize={pageSize}
        total={total}
        onPageChange={setPageNumber}
        onPageSizeChange={changePageSize}
        disabled={loading}
      />
    </div>
  );
}
