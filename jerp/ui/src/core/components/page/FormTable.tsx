import * as React from 'react';

import { model } from '../../model';
import { cacheClient } from '../../cache';
import type { FieldDescriptor } from '../../types';
import { Table, type TableInlineEdit } from './Table';
import { FormContext, FormTabContext } from './context';
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


/** A table of child records filtered by the current form record. */
export function FormTable({
  model: modelName,
  emptyMessage = 'No records.',
  createLabel = 'Add',
  canCreate = true,
  canEdit = true,
  canDelete = true,
  children,
}: FormTableProps) {
  const form = React.useContext(FormContext);
  const schema = useModelFields(modelName);
  const parentModel = form?.model;
  const rawParentId = form?.recordId ?? form?.values?.id ?? null;
  const parentId =
    typeof rawParentId === 'string' || typeof rawParentId === 'number'
      ? rawParentId
      : null;

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

  const [mode, setMode] = React.useState<'create' | 'edit' | null>(null);
  const [editingId, setEditingId] = React.useState<number | string | null>(null);
  const [focusField, setFocusField] = React.useState<string | null>(null);
  const [values, setValues] = React.useState<Record<string, unknown>>({});
  const [errors, setErrors] = React.useState<FormErrors>({});
  const [saving, setSaving] = React.useState(false);
  const [formError, setFormError] = React.useState<string | null>(null);
  const [revision, setRevision] = React.useState(0);
  const cache = React.useMemo(
    () =>
      relationField
        ? cacheClient(modelName, relationField.name, parentId)
        : undefined,
    [modelName, relationField?.name, parentId],
  );

  React.useEffect(() => {
    if (!relationField || !form?.registerCommit || !cache) {
      return;
    }
    return form.registerCommit(async (recordId) => {
      await cache.commit(relationField.name, recordId);
    });
  }, [relationField, form?.registerCommit, cache]);

  const initialValues = () => {
    const initial: Record<string, unknown> = {};
    for (const field of editFields) {
      if (field.default !== undefined) {
        initial[field.name] = field.default;
      }
    }
    return initial;
  };

  const openCreate = () => {
    setMode('create');
    setEditingId(null);
    setFocusField(editFields[0]?.name ?? null);
    setValues(initialValues());
    setErrors({});
    setFormError(null);
  };

  const openEdit = async (id: string, fieldName?: string) => {
    setFormError(null);
    try {
      const source = cache ?? model(modelName);
      const record = await source.find<Record<string, unknown>>(id);
      if (!record) {
        setFormError('Record not found.');
        return;
      }
      const target =
        fieldName && editFields.some((field) => field.name === fieldName)
          ? fieldName
          : editFields[0]?.name ?? null;
      setMode('edit');
      setEditingId(id);
      setFocusField(target);
      setValues(record);
      setErrors({});
    } catch (err) {
      setFormError((err as Error).message);
    }
  };

  const close = () => {
    setMode(null);
    setEditingId(null);
    setFocusField(null);
    setValues({});
    setErrors({});
    setFormError(null);
  };

  const changeValue = (name: string, value: unknown) => {
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => {
      if (!current[name]) {
        return current;
      }
      const next = { ...current };
      delete next[name];
      return next;
    });
  };

  const save = async () => {
    if (!mode || saving || !relationField) {
      return;
    }
    const nextErrors = validateValues(
      editFields.map((field) => ({ field, value: values[field.name] })),
    );
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      setFormError(null);
      return;
    }

    setSaving(true);
    setFormError(null);
    try {
      const source = cache ?? model(modelName);
      const payload: Record<string, unknown> = {};
      for (const field of editFields) {
        payload[field.name] = values[field.name];
      }
      if (mode === 'edit' && editingId !== null) {
        await source.update(editingId, payload);
      } else {
        await source.create(payload);
      }
      setRevision((value) => value + 1);
      setMode(null);
      setEditingId(null);
      setFocusField(null);
      setValues({});
      setErrors({});
    } catch (err) {
      setFormError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  if (!form) {
    return (
      <p className="text-sm text-slate-500">
        FormTable must be used inside a Form.
      </p>
    );
  }

  if (schema.length === 0) {
    return <p className="text-sm text-slate-400">Loading…</p>;
  }

  if (!parentModel || !relationField) {
    return (
      <p className="text-sm text-slate-500">
        No relation field to &quot;{parentModel ?? 'the parent model'}&quot; was
        found on {modelName}.
      </p>
    );
  }

  const inlineEdit: TableInlineEdit | undefined = mode
    ? {
        mode,
        editingId,
        focusField,
        values,
        errors,
        editableFields: editFields.map((field) => field.name),
        saving,
        onChange: changeValue,
        onSave: () => void save(),
        onCancel: close,
      }
    : undefined;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <button
          type="button"
          className="rounded bg-brand-blue px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-blue-dark disabled:opacity-40"
          disabled={!canCreate || Boolean(mode)}
          onClick={openCreate}
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
          model={modelName}
          client={cache}
          emptyMessage={emptyMessage}
          inlineEdit={inlineEdit}
          refreshKey={revision}
          onCellClick={
            canEdit
              ? (record, field) =>
                  void openEdit(String(record.id), field)
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
