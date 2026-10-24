import * as React from 'react';

import { t } from '../../i18n';
import { model, type DraftChange, type DraftRecord } from '../../model';
import { clearDraftToken, draftToken, DraftQueue } from '../../draft';
import { FieldHelp } from '../fields/FieldHelp';
import { fieldRegistry } from '../fields/registry';
import {
  DraftContext,
  RecordContext,
  FormTabContext,
  usePage,
  type DraftQueueHandle,
} from './context';
import { validateValues, type FormErrors } from './validation';
import { isAction, type ActionProps } from './Action';
import { autoModelFields, useModelFields } from './useModelFields';

export interface FormFieldProps {
  name: string;
  label?: string;
  ttype?: string;
}

/** Declares a form field. Renders nothing on its own. */
export function FormField(_props: FormFieldProps) {
  return null;
}

export function isFormField(node: React.ReactNode): node is React.ReactElement<FormFieldProps> {
  return React.isValidElement(node) && node.type === FormField;
}

export interface FormGroupProps {
  label?: string;
  children?: React.ReactNode;
}

/** Groups fields into a labelled section. Rendered by Form. */
export function FormGroup({ children }: FormGroupProps) {
  return <>{children}</>;
}

export function isFormGroup(node: React.ReactNode): node is React.ReactElement<FormGroupProps> {
  return React.isValidElement(node) && node.type === FormGroup;
}

export interface FormTabProps {
  label: string;
  children?: React.ReactNode;
}

/** Declares a tab inside ``FormTabs``. Renders nothing on its own. */
export function FormTab(_props: FormTabProps) {
  return null;
}

export function isFormTab(node: React.ReactNode): node is React.ReactElement<FormTabProps> {
  return React.isValidElement(node) && node.type === FormTab;
}

export interface FormTabsProps {
  children?: React.ReactNode;
}

/** Declares a tabbed section. Rendered by Form. */
export function FormTabs(_props: FormTabsProps) {
  return null;
}

export function isFormTabs(node: React.ReactNode): node is React.ReactElement<FormTabsProps> {
  return React.isValidElement(node) && node.type === FormTabs;
}

function FormTabsSection({
  tabs,
  renderNodes,
}: {
  tabs: React.ReactElement<FormTabProps>[];
  renderNodes: (nodes: React.ReactNode) => React.ReactNode;
}) {
  const [active, setActive] = React.useState(0);
  if (tabs.length === 0) {
    return null;
  }

  const selected = Math.min(active, tabs.length - 1);
  return (
    <div className="md:col-span-2">
      <div className="flex flex-wrap gap-1 border-b border-slate-200" role="tablist">
        {tabs.map((tab, index) => (
          <button
            key={index}
            type="button"
            role="tab"
            aria-selected={index === selected}
            onClick={() => setActive(index)}
            className={`-mb-px rounded-t border-b-2 px-4 py-2 text-sm font-medium ${
              index === selected
                ? 'border-brand-blue text-brand-blue'
                : 'border-transparent text-slate-500 hover:text-brand-navy'
            }`}
          >
            {tab.props.label}
          </button>
        ))}
      </div>
      {tabs.map((tab, index) => (
        <div
          key={index}
          className="grid grid-cols-1 gap-4 pt-4 md:grid-cols-2"
          role="tabpanel"
          hidden={index !== selected}
        >
          <FormTabContext.Provider value={true}>
            {renderNodes(tab.props.children)}
          </FormTabContext.Provider>
        </div>
      ))}
    </div>
  );
}

/** Flatten fields, descending into groups and tabs. */
function collectFields(nodes: React.ReactNode): React.ReactElement<FormFieldProps>[] {
  const out: React.ReactElement<FormFieldProps>[] = [];
  for (const node of React.Children.toArray(nodes)) {
    if (isFormField(node)) {
      out.push(node);
    } else if (isFormGroup(node)) {
      out.push(...collectFields(node.props.children));
    } else if (isFormTabs(node)) {
      out.push(...collectFields(node.props.children));
    } else if (isFormTab(node)) {
      out.push(...collectFields(node.props.children));
    }
  }
  return out;
}

function ActionMenu({
  actions,
  onSelect,
}: {
  actions: React.ReactElement<ActionProps>[];
  onSelect: (action: React.ReactElement<ActionProps>) => void;
}) {
  const [open, setOpen] = React.useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        aria-label={t('app.actions')}
        onClick={() => setOpen((value) => !value)}
        className="rounded px-2 py-1 text-lg leading-none text-slate-500 hover:bg-slate-100"
      >
        ⋯
      </button>
      {open ? (
        <div className="absolute right-0 top-full z-30 mt-1 min-w-44 rounded-md border border-slate-200 bg-white py-1 shadow-lg">
          {actions.map((action, index) => (
            <button
              key={index}
              type="button"
              className="block w-full px-3 py-1.5 text-left text-sm text-slate-700 hover:bg-slate-50"
              onClick={() => {
                setOpen(false);
                onSelect(action);
              }}
            >
              {action.props.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export interface FormProps {
  model?: string;
  title?: string;
  recordId?: number | string | null;
  readonly?: boolean;
  /** Values applied when creating a new draft. */
  defaults?: Record<string, unknown>;
  children?: React.ReactNode;
  onSaved?: () => void;
}

/**
 * A form bound to a model. Shown when the page's view type is ``form``; loads the
 * record from the page's ``id`` and saves (create/update) via the model API.
 * ``<Action>`` children appear in a ⋯ menu in the header.
 */
export function Form({
  model: modelName,
  title,
  recordId: recordIdProp,
  readonly,
  defaults,
  children,
  onSaved,
}: FormProps) {
  const page = usePage();
  const explicitRecord = recordIdProp !== undefined && recordIdProp !== null;
  const active = explicitRecord || !page || page.view === 'form';
  const recordId = recordIdProp ?? page?.id ?? null;
  const editing = recordId !== null && recordId !== undefined;
  const isReadonly = readonly ?? !(page?.update ?? true);

  const fields = collectFields(children);
  const actions = React.Children.toArray(children).filter(isAction);
  const schema = useModelFields(modelName);
  const autoEnabled = page?.autoFields ?? true;
  const autoFields = React.useMemo(
    () =>
      autoEnabled
        ? autoModelFields(schema, new Set(fields.map((field) => field.props.name)))
        : [],
    [autoEnabled, schema, fields],
  );
  const types = React.useMemo(() => {
    const map: Record<string, string> = {};
    for (const descriptor of schema) {
      map[descriptor.name] = descriptor.ttype;
    }
    return map;
  }, [schema]);

  const token = React.useMemo(
    () =>
      modelName ? draftToken(modelName, recordId, page?.name) : '',
    [modelName, recordId, page?.name],
  );
  const [draft, setDraft] = React.useState<DraftRecord | null>(null);
  const [values, setValues] = React.useState<Record<string, unknown>>({});
  const [busy, setBusy] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [errors, setErrors] = React.useState<FormErrors>({});
  const [warnings, setWarnings] = React.useState<unknown[]>([]);
  const [draftsVersion, setDraftsVersion] = React.useState(0);
  const [activeAction, setActiveAction] = React.useState<React.ReactElement<ActionProps> | null>(null);
  const queuesRef = React.useRef<Set<DraftQueueHandle>>(new Set());
  const parentQueueRef = React.useRef<DraftQueue | null>(null);
  const defaultsRef = React.useRef(defaults);
  defaultsRef.current = defaults;

  const notifyDraftsChanged = React.useCallback(() => {
    setDraftsVersion((value) => value + 1);
  }, []);

  const registerQueue = React.useCallback((queue: DraftQueueHandle) => {
    queuesRef.current.add(queue);
    return () => {
      queuesRef.current.delete(queue);
      queue.dispose();
    };
  }, []);

  const flushAll = React.useCallback(async () => {
    for (const queue of Array.from(queuesRef.current)) {
      await queue.flush();
    }
  }, []);

  const discardAll = React.useCallback(async () => {
    if (!modelName || !token) {
      return;
    }
    await model(modelName).discardAllDrafts(token);
    clearDraftToken(modelName, recordId, page?.name);
    for (const queue of Array.from(queuesRef.current)) {
      queue.dispose();
    }
    queuesRef.current.clear();
    setDraft(null);
    setValues({});
    setErrors({});
    setWarnings([]);
  }, [modelName, token, recordId, page?.name]);

  React.useEffect(() => {
    if (!active || !modelName || !token) {
      return;
    }
    let cancelled = false;
    let queue: DraftQueue | null = null;
    setLoading(true);
    setError(null);

    if (isReadonly) {
      void (async () => {
        try {
          if (editing) {
            const record = await model(modelName).find<Record<string, unknown>>(
              recordId as number | string,
            );
            if (!cancelled) {
              setValues(record ?? {});
            }
          } else if (!cancelled) {
            setValues({});
          }
          if (!cancelled) {
            setDraft(null);
            setErrors({});
            setWarnings([]);
          }
        } catch (err) {
          if (!cancelled) {
            setError((err as Error).message);
          }
        } finally {
          if (!cancelled) {
            setLoading(false);
          }
        }
      })();
      return () => {
        cancelled = true;
      };
    }

    void (async () => {
      try {
        const client = model(modelName);
        const loaded = editing
          ? await client.editDraft(
              recordId as number | string,
              token,
            )
          : await client.newDraft(token, defaultsRef.current);
        if (cancelled) {
          return;
        }
        setDraft(loaded);
        setValues(loaded.values ?? {});
        setErrors({});
        setWarnings([]);

        queue = new DraftQueue(
          modelName,
          loaded.id,
          (change: DraftChange) => {
            const pending = queue?.pendingValues() ?? {};
            setValues((current) => ({
              ...current,
              ...change.values,
              ...pending,
            }));
            setErrors(change.errors ?? {});
            setWarnings(change.warnings ?? []);
            setDraft((current) =>
              current
                ? {
                    ...current,
                    values: change.values,
                    dirty: change.dirty,
                    version: change.version,
                  }
                : current,
            );
            setDraftsVersion((value) => value + 1);
          },
          (err) => setError(err.message),
        );
        parentQueueRef.current = queue;
        queuesRef.current.add(queue);
      } catch (err) {
        if (!cancelled) {
          setError((err as Error).message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
      if (queue) {
        queuesRef.current.delete(queue);
        queue.dispose();
      }
      if (parentQueueRef.current === queue) {
        parentQueueRef.current = null;
      }
    };
  }, [active, modelName, recordId, editing, token, isReadonly]);

  React.useEffect(() => {
    if (!active || !modelName || !token || !draft || draftsVersion === 0) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const rows = await model(modelName).drafts(token);
        const current = rows.find((row) => row.id === draft.id);
        if (!current || cancelled) {
          return;
        }
        const pending = parentQueueRef.current?.pendingValues() ?? {};
        setValues((state) => ({ ...state, ...current.values, ...pending }));
        setDraft((state) =>
          state
            ? {
                ...state,
                values: current.values,
                dirty: current.dirty,
                version: current.version,
              }
            : state,
        );
      } catch {
        // The parent values stay as they are; the next change retries.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [draftsVersion, active, modelName, token, draft?.id]);

  if (!active) {
    return null;
  }

  const saved =
    onSaved ??
    (() => {
      if (editing) {
        window.location.reload();
      } else {
        page?.setView('list');
      }
    });

  const submit = async () => {
    if (!modelName || busy || loading || !draft) {
      return;
    }

    const entries: Array<{ field: (typeof schema)[number]; value: unknown }> = [];
    for (const formField of fields) {
      const name = formField.props.name;
      const descriptor =
        schema.find((item) => item.name === name) ?? {
          name,
          label: formField.props.label ?? name,
          ttype: formField.props.ttype ?? types[name] ?? 'char',
        };
      entries.push({ field: descriptor, value: values[name] });
    }
    for (const descriptor of autoFields) {
      entries.push({ field: descriptor, value: values[descriptor.name] });
    }
    const nextErrors = validateValues(entries);
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      setError(null);
      return;
    }

    setErrors({});
    setBusy(true);
    setError(null);
    try {
      await flushAll();
      const combinedErrors: FormErrors = {};
      for (const queue of Array.from(queuesRef.current)) {
        Object.assign(combinedErrors, queue.lastErrors ?? {});
      }
      if (Object.keys(combinedErrors).length > 0) {
        setErrors(combinedErrors);
        setBusy(false);
        return;
      }
      await model(modelName).commitDrafts(token);
      clearDraftToken(modelName, recordId, page?.name);
      for (const queue of Array.from(queuesRef.current)) {
        queue.dispose();
      }
      queuesRef.current.clear();
      saved();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const discard = async () => {
    if (!modelName || busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await discardAll();
      saved();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const updateValue = (name: string, value: unknown) => {
    setValues((state) => ({ ...state, [name]: value }));
    setErrors((current) => {
      if (!current[name]) {
        return current;
      }
      const next = { ...current };
      delete next[name];
      return next;
    });
    parentQueueRef.current?.setField(name, value);
  };

  const renderField = (
    name: string,
    labelProp: string | undefined,
    ttype: string,
    key: React.Key,
    readonlyField = false,
  ) => {
    const descriptor = schema.find((item) => item.name === name);
    const label = labelProp ?? descriptor?.label ?? name;
    const readonly = isReadonly || readonlyField || Boolean(descriptor?.readonly);
    const Widget = fieldRegistry.get(ttype) ?? fieldRegistry.get('char');
    const widgetField = {
      ...(descriptor ?? { name, label, ttype }),
      name,
      label,
      ttype,
      readonly,
    };
    return (
      <div key={key} className="block">
        <div className="mb-1 flex items-center gap-1.5">
          <span className="text-sm font-medium text-brand-navy">{label}</span>
          {descriptor?.help ? <FieldHelp text={descriptor.help} /> : null}
        </div>
        {Widget ? (
          <Widget
            field={widgetField}
            value={values[name]}
            readonly={readonly}
            model={modelName}
            recordId={recordId}
            onChange={(value) => updateValue(name, value)}
          />
        ) : null}
        {errors[name] ? (
          <p className="mt-1 text-xs text-red-600">{errors[name]}</p>
        ) : null}
      </div>
    );
  };

  const renderNodes = (nodes: React.ReactNode): React.ReactNode =>
    React.Children.toArray(nodes).map((node, index) => {
      if (isAction(node)) {
        return null; // actions are shown in the ⋯ menu
      }
      if (isFormField(node)) {
        const name = node.props.name;
        return renderField(
          name,
          node.props.label,
          node.props.ttype ?? types[name] ?? 'char',
          index,
        );
      }
      if (isFormGroup(node)) {
        return (
          <fieldset
            key={index}
            className="rounded-lg border border-slate-200 p-4 md:col-span-2"
          >
            {node.props.label ? (
              <legend className="px-1 text-sm font-medium text-brand-navy">
                {node.props.label}
              </legend>
            ) : null}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {renderNodes(node.props.children)}
            </div>
          </fieldset>
        );
      }
      if (isFormTabs(node)) {
        const tabs = React.Children.toArray(node.props.children).filter(isFormTab);
        return (
          <FormTabsSection key={index} tabs={tabs} renderNodes={renderNodes} />
        );
      }
      return (
        <div key={index} className="md:col-span-2">
          {node}
        </div>
      );
    });

  return (
    <DraftContext.Provider
      value={{
        token,
        model: modelName,
        draftId: draft?.id ?? null,
        recordId: draft?.record_id ?? recordId,
        values,
        registerQueue,
        flushAll,
        discardAll,
        draftsVersion,
        notifyDraftsChanged,
      }}
    >
      <RecordContext.Provider value={values}>
        <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
        <div className="flex items-center justify-between gap-3">
          {title ? <h3 className="text-base font-semibold">{title}</h3> : <span />}
          <div className="flex items-center gap-2">
            {actions.length > 0 ? (
              <ActionMenu actions={actions} onSelect={setActiveAction} />
            ) : null}
            {!isReadonly && draft ? (
              <button
                type="button"
                className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:border-brand-cyan hover:bg-brand-cyan/5 disabled:opacity-40"
                disabled={busy || loading}
                onClick={() => void discard()}
              >
                {t('app.discard')}
              </button>
            ) : null}
            {!isReadonly ? (
              <button
                type="button"
                className="rounded bg-brand-blue px-4 py-2 text-sm font-medium text-white hover:bg-brand-blue-dark disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60"
                disabled={busy || loading || !draft}
                onClick={() => void submit()}
              >
                {busy
                  ? t('app.saving')
                  : loading
                    ? t('app.loading_text')
                    : t('app.save')}
              </button>
            ) : null}
          </div>
        </div>

        {error ? (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {warnings.length > 0 ? (
          <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            {warnings.map((warning, index) => (
              <p key={index}>{String(warning)}</p>
            ))}
          </div>
        ) : null}

        {Object.keys(errors).length > 0 ? (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            <ul className="list-disc space-y-1 pl-4">
              {Object.values(errors).map((message, index) => (
                <li key={index}>{message}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {renderNodes(children)}
          {autoFields.length > 0 ? (
            <fieldset className="rounded-lg border border-slate-200 p-4 md:col-span-2">
              <legend className="px-1 text-sm font-medium text-brand-navy">
                {t('app.additional_fields')}
              </legend>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {autoFields.map((field, index) =>
                  renderField(
                    field.name,
                    field.label ?? field.name,
                    field.ttype,
                    `auto-${index}`,
                    Boolean(field.readonly),
                  ),
                )}
              </div>
            </fieldset>
          ) : null}
        </div>
      </div>

      {activeAction
        ? React.cloneElement(activeAction, {
            open: true,
            onClose: () => setActiveAction(null),
          })
        : null}
      </RecordContext.Provider>
    </DraftContext.Provider>
  );
}
