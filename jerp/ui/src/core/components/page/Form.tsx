import * as React from 'react';

import { model, type DataClient } from '../../model';
import { FieldHelp } from '../fields/FieldHelp';
import { fieldRegistry } from '../fields/registry';
import { RecordContext, FormContext, FormTabContext, usePage } from './context';
import { validateValues, type FormErrors } from './validation';
import { Action, isAction, type ActionProps } from './Action';
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
        aria-label="Actions"
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
  /** Values applied when creating a new record (not used when editing). */
  defaults?: Record<string, unknown>;
  /** Optional data source; defaults to the model API. */
  client?: DataClient;
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
  client,
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

  const [values, setValues] = React.useState<Record<string, unknown>>({});
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [errors, setErrors] = React.useState<FormErrors>({});
  const [refreshToken, setRefreshToken] = React.useState(0);
  const [activeAction, setActiveAction] = React.useState<React.ReactElement<ActionProps> | null>(null);
  const commitHandlers = React.useRef(
    new Set<(recordId: number | string) => Promise<void>>(),
  );

  const refresh = React.useCallback(() => {
    setRefreshToken((value) => value + 1);
  }, []);

  const registerCommit = React.useCallback(
    (handler: (recordId: number | string) => Promise<void>) => {
      commitHandlers.current.add(handler);
      return () => {
        commitHandlers.current.delete(handler);
      };
    },
    [],
  );

  React.useEffect(() => {
    if (!active || !modelName) {
      return;
    }
    let cancelled = false;

    void (async () => {
      if (editing) {
        try {
          const source = client ?? model(modelName);
          const record = await source.find<Record<string, unknown>>(
            recordId as number,
          );
          if (!cancelled) {
            setValues(record ?? {});
            setErrors({});
            setError(null);
          }
        } catch {
          // ignore
        }
      } else if (!cancelled) {
        setValues({});
        setErrors({});
        setError(null);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [active, modelName, recordId, editing, refreshToken, client]);

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
    if (!modelName || busy) {
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
      const payload: Record<string, unknown> = {};
      for (const field of fields) {
        payload[field.props.name] = values[field.props.name];
      }
      for (const field of autoFields) {
        payload[field.name] = values[field.name];
      }
      const source = client ?? model(modelName);
      if (editing) {
        await source.update(recordId as number, payload);
        for (const handler of Array.from(commitHandlers.current)) {
          await handler(recordId as number | string);
        }
      } else {
        const created = await source.create({
          ...(defaults ?? {}),
          ...payload,
        });
        const createdId = (created as { id?: number | string } | null)?.id;
        if (createdId !== undefined && createdId !== null) {
          for (const handler of Array.from(commitHandlers.current)) {
            await handler(createdId);
          }
        }
      }
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
    <FormContext.Provider
      value={{ model: modelName, recordId, values, refresh, registerCommit }}
    >
      <RecordContext.Provider value={values}>
        <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
        <div className="flex items-center justify-between gap-3">
          {title ? <h3 className="text-base font-semibold">{title}</h3> : <span />}
          <div className="flex items-center gap-2">
            {actions.length > 0 ? (
              <ActionMenu actions={actions} onSelect={setActiveAction} />
            ) : null}
            {!isReadonly ? (
              <button
                type="button"
                className="rounded bg-brand-blue px-4 py-2 text-sm font-medium text-white hover:bg-brand-blue-dark disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60"
                disabled={busy}
                onClick={() => void submit()}
              >
                {busy ? 'Saving…' : 'Save'}
              </button>
            ) : null}
          </div>
        </div>

        {error ? (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
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
                Additional fields
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
    </FormContext.Provider>
  );
}
