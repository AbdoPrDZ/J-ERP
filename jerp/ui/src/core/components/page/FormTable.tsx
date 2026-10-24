import * as React from 'react';

import { t } from '../../i18n';
import { model } from '../../model';
import type {
  DataClient,
  DraftChange,
  DraftRecord,
  ListParams,
} from '../../model';
import { DraftQueue } from '../../draft';
import type { FieldDescriptor } from '../../types';
import { Table, type TableInlineEdit } from './Table';
import { DraftContext, FormTabContext } from './context';
import { useModelFields } from './useModelFields';
import { validateValues, type FormErrors } from './validation';

export interface FormTableProps {
  model: string;
  emptyMessage?: string;
  createLabel?: string;
  canCreate?: boolean;
  canEdit?: boolean;
  canDelete?: boolean;
  children?: React.ReactNode;
}

interface DraftRow extends Record<string, unknown> {
  id: string;
  _record_id?: number | null;
  _draft_id?: number;
  _draft_record?: DraftRecord;
}

function compareValues(a: unknown, b: unknown): number {
  if (a === b) {
    return 0;
  }
  if (a === null || a === undefined) {
    return 1;
  }
  if (b === null || b === undefined) {
    return -1;
  }
  if (typeof a === 'number' && typeof b === 'number') {
    return a - b;
  }
  return String(a).localeCompare(String(b));
}

function sortRows(rows: DraftRow[], order?: string) {
  if (!order) {
    return rows;
  }
  const specs = order
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
  for (const spec of [...specs].reverse()) {
    const [name, direction] = spec.split(/\s+/);
    const reverse = String(direction ?? '').toLowerCase() === 'desc';
    rows.sort((left, right) => {
      const result = compareValues(left[name], right[name]);
      return reverse ? -result : result;
    });
  }
  return rows;
}

interface DraftRowsClient extends DataClient {
  invalidate: () => void;
}

function makeRowsClient(
  childModel: string,
  token: string,
  parentModel: string,
  parentDraftId: number | null,
  parentRecordId: number | string | null,
  relationField: string,
): DraftRowsClient {
  let rows: DraftRow[] = [];
  let loaded = false;
  let loading: Promise<void> | null = null;

  const load = async () => {
    if (loaded) {
      return;
    }
    if (!loading) {
      loading = (async () => {
        const realRows = parentRecordId
          ? await model(childModel).all<Record<string, unknown>>({
              domain: [[relationField, '=', parentRecordId]],
            })
          : [];
        const realIds = new Set(realRows.map((row) => String(row.id)));
        const drafts = (await model(childModel).drafts(token)).filter(
          (draft) => draft.model === childModel,
        );
        const byRecord = new Map<string, DraftRecord>();
        for (const draft of drafts) {
          if (draft.record_id !== null && draft.record_id !== undefined) {
            byRecord.set(String(draft.record_id), draft);
          }
        }

        const merged: DraftRow[] = [];
        for (const real of realRows) {
          const draft = byRecord.get(String(real.id));
          if (draft?.state === 'delete') {
            continue;
          }
          merged.push({
            ...real,
            ...(draft?.state === 'update' ? draft.values : {}),
            id: `record:${String(real.id)}`,
            _record_id: Number(real.id),
            _draft_id: draft?.id,
            _draft_record: draft,
          });
        }

        for (const draft of drafts) {
          if (draft.state !== 'create') {
            continue;
          }
          const relationValue = draft.values[relationField];
          const belongs =
            (parentDraftId !== null &&
              relationValue === `draft:${parentDraftId}`) ||
            (parentRecordId !== null &&
              String(relationValue) === String(parentRecordId)) ||
            (parentRecordId === null && relationValue === undefined);
          if (!belongs) {
            continue;
          }
          merged.unshift({
            ...draft.values,
            id: `draft:${draft.id}`,
            _record_id: null,
            _draft_id: draft.id,
            _draft_record: draft,
          });
        }

        rows = merged;
        loaded = true;
      })();
    }
    await loading;
  };

  const remove = async (id: number | string) => {
    const key = String(id);
    if (key.startsWith('draft:')) {
      const draftId = Number(key.slice(6));
      await model(childModel).discardDraft(draftId);
    } else if (key.startsWith('record:')) {
      const recordId = key.slice(7);
      await model(childModel).removeDraft(token, recordId);
    } else {
      return false;
    }
    loaded = false;
    loading = null;
    return true;
  };

  return {
    async all<T = Record<string, unknown>>(params: ListParams = {}) {
      await load();
      let result = [...rows];
      result = sortRows(result, params.order);
      const offset = params.offset ?? 0;
      if (offset) {
        result = result.slice(offset);
      }
      if (params.limit !== undefined) {
        result = result.slice(0, params.limit);
      }
      return result as T[];
    },
    async count() {
      await load();
      return rows.length;
    },
    async find<T = Record<string, unknown>>(id: number | string) {
      await load();
      return (rows.find((row) => row.id === String(id)) ?? null) as T | null;
    },
    async create() {
      throw new Error('FormTable creates records through the draft API.');
    },
    async update() {
      throw new Error('FormTable edits records through the draft API.');
    },
    delete: remove,
    async deleteMany(ids) {
      let count = 0;
      for (const id of ids) {
        if (await remove(id)) {
          count += 1;
        }
      }
      return count;
    },
    async call<T = unknown>(
      func: string,
      params: Record<string, unknown> = {},
    ) {
      if (func === 'delete') {
        return (await remove(params.id as number | string)) as unknown as T;
      }
      throw new Error(`Unsupported FormTable action "${func}".`);
    },
    invalidate() {
      loaded = false;
      loading = null;
    },
  };
}

/** A table of related records backed by server-side drafts. */
export function FormTable({
  model: childModel,
  emptyMessage = t('app.no_records'),
  createLabel = t('app.add'),
  canCreate = true,
  canEdit = true,
  canDelete = true,
  children,
}: FormTableProps) {
  const draftContext = React.useContext(DraftContext);
  const schema = useModelFields(childModel);
  const parentModel = draftContext?.model;
  const parentDraftId = draftContext?.draftId ?? null;
  const parentRecordId = draftContext?.recordId ?? null;
  const token = draftContext?.token;

  const relationField = React.useMemo(() => {
    if (!parentModel) {
      return undefined;
    }
    const preferred = `${parentModel.split('.').pop()}_id`;
    return (
      schema.find(
        (field) =>
          field.name === preferred &&
          field.ttype === 'many2one' &&
          field.relation === parentModel,
      ) ??
      schema.find(
        (field) =>
          field.ttype === 'many2one' && field.relation === parentModel,
      )
    );
  }, [schema, parentModel]);

  const editFields = React.useMemo<FieldDescriptor[]>(() => {
    const excluded = new Set(
      ['id', 'created_at', 'updated_at', relationField?.name].filter(
        (name): name is string => Boolean(name),
      ),
    );
    return schema.filter(
      (field) =>
        !excluded.has(field.name) && !field.readonly && !field.hide,
    );
  }, [schema, relationField?.name]);

  const client = React.useMemo(
    () =>
      token && parentModel && relationField
        ? makeRowsClient(
            childModel,
            token,
            parentModel,
            parentDraftId,
            parentRecordId,
            relationField.name,
          )
        : undefined,
    [
      childModel,
      token,
      parentModel,
      parentDraftId,
      parentRecordId,
      relationField?.name,
    ],
  );

  const [editor, setEditor] = React.useState<{
    draft: DraftRecord;
    values: Record<string, unknown>;
    errors: FormErrors;
    saving: boolean;
    focusField: string | null;
  } | null>(null);
  const [formError, setFormError] = React.useState<string | null>(null);
  const [revision, setRevision] = React.useState(0);
  const queueRef = React.useRef<DraftQueue | null>(null);
  const unregisterRef = React.useRef<(() => void) | null>(null);

  React.useEffect(
    () => () => {
      queueRef.current?.dispose();
      unregisterRef.current?.();
    },
    [],
  );

  const disposeEditor = () => {
    queueRef.current?.dispose();
    queueRef.current = null;
    unregisterRef.current?.();
    unregisterRef.current = null;
  };

  const refreshRows = () => {
    client?.invalidate();
    setRevision((value) => value + 1);
    draftContext?.notifyDraftsChanged();
  };

  const openDraft = (draft: DraftRecord, focusField?: string | null) => {
    if (!draftContext) {
      return;
    }
    disposeEditor();
    setFormError(null);
    const queue = new DraftQueue(
      draft.model,
      draft.id,
      (change: DraftChange) => {
        const pending = queue.pendingValues();
        setEditor((current) =>
          current
            ? {
                ...current,
                values: {
                  ...current.values,
                  ...change.values,
                  ...pending,
                },
                errors: change.errors ?? {},
                draft: {
                  ...current.draft,
                  values: change.values,
                  dirty: change.dirty,
                  version: change.version,
                },
              }
            : current,
        );
      },
      (err) => setFormError(err.message),
    );
    queueRef.current = queue;
    unregisterRef.current = draftContext.registerQueue(queue);
    setEditor({
      draft,
      values: draft.values,
      errors: {},
      saving: false,
      focusField: focusField ?? editFields[0]?.name ?? null,
    });
  };

  const finishEditor = async (commit: boolean): Promise<boolean> => {
    if (!editor) {
      return false;
    }
    setEditor((current) => (current ? { ...current, saving: true } : current));
    try {
      if (commit) {
        const nextErrors = validateValues(
          editFields.map((field) => ({
            field,
            value: editor.values[field.name],
          })),
        );
        if (Object.keys(nextErrors).length > 0) {
          setEditor((current) =>
            current
              ? { ...current, errors: nextErrors, saving: false }
              : current,
          );
          return false;
        }
        const queue = queueRef.current;
        await queue?.flush();
        const queueErrors = queue?.lastErrors ?? {};
        if (Object.keys(queueErrors).length > 0) {
          setEditor((current) =>
            current
              ? { ...current, errors: queueErrors, saving: false }
              : current,
          );
          return false;
        }
      }
      disposeEditor();
      setEditor(null);
      refreshRows();
      return true;
    } catch (err) {
      setFormError((err as Error).message);
      setEditor((current) => (current ? { ...current, saving: false } : current));
      return false;
    }
  };

  const cancelEditor = async () => {
    if (!editor) {
      return;
    }
    const draftId = editor.draft.id;
    disposeEditor();
    setEditor(null);
    try {
      await model(childModel).discardDraft(draftId);
    } catch (err) {
      setFormError((err as Error).message);
    }
    refreshRows();
  };

  const addRecord = async () => {
    if (!token || !relationField || !draftContext) {
      return;
    }
    setFormError(null);
    try {
      if (editor) {
        const ok = await finishEditor(true);
        if (!ok) {
          return;
        }
      }
      const draft = await model(childModel).newDraft(
        token,
        {
          [relationField.name]: `draft:${parentDraftId}`,
        },
        false,
      );
      refreshRows();
      openDraft(draft, editFields[0]?.name ?? null);
    } catch (err) {
      setFormError((err as Error).message);
    }
  };

  const editRow = async (row: DraftRow, fieldName: string) => {
    if (!token || !relationField) {
      return;
    }
    try {
      if (editor) {
        const ok = await finishEditor(true);
        if (!ok) {
          return;
        }
      }
      let draft = row._draft_record;
      if (!draft) {
        const recordId = row._record_id;
        if (recordId === null || recordId === undefined) {
          return;
        }
        draft = await model(childModel).editDraft(recordId, token);
      }
      const focus =
        fieldName && editFields.some((field) => field.name === fieldName)
          ? fieldName
          : editFields[0]?.name ?? null;
      openDraft(draft, focus);
      refreshRows();
    } catch (err) {
      setFormError((err as Error).message);
    }
  };

  if (!draftContext) {
    return (
      <p className="text-sm text-slate-500">
        {t('app.form_table_requires_form')}
      </p>
    );
  }

  if (schema.length === 0) {
    return <p className="text-sm text-slate-400">{t('app.loading_text')}</p>;
  }

  if (!parentModel || !relationField || !client) {
    return (
      <p className="text-sm text-slate-500">
        {t('app.form_table_missing_relation', {
          parent: parentModel ?? t('app.parent_model'),
          child: childModel,
        })}
      </p>
    );
  }

  const inlineEdit: TableInlineEdit | undefined = editor
    ? {
        mode: editor.draft.state === 'create' ? 'create' : 'edit',
        editingId:
          editor.draft.state === 'create'
            ? `draft:${editor.draft.id}`
            : `record:${String(editor.draft.record_id)}`,
        focusField: editor.focusField,
        values: editor.values,
        errors: editor.errors,
        editableFields: editFields.map((field) => field.name),
        saving: editor.saving,
        onChange: (name, value) => {
          setEditor((current) =>
            current
              ? { ...current, values: { ...current.values, [name]: value } }
              : current,
          );
          queueRef.current?.setField(name, value);
        },
        onSave: () => void finishEditor(true),
        onCancel: () => void cancelEditor(),
      }
    : undefined;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <button
          type="button"
          className="rounded bg-brand-blue px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-blue-dark disabled:opacity-40"
          disabled={!canCreate || Boolean(editor) || parentDraftId === null}
          onClick={() => void addRecord()}
        >
          {createLabel}
        </button>
      </div>

      {formError ? (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {formError}
        </div>
      ) : null}

      <FormTabContext.Provider value={true}>
        <Table
          model={childModel}
          client={client}
          emptyMessage={emptyMessage}
          inlineEdit={inlineEdit}
          refreshKey={revision}
          onCellClick={
            canEdit
              ? (record, field) =>
                  void editRow(record as DraftRow, field)
              : undefined
          }
          selectable={false}
          allowDelete={canDelete}
        >
          {children}
        </Table>
      </FormTabContext.Provider>
    </div>
  );
}
