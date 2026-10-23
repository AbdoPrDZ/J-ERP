import * as React from 'react';

import { model } from '../../model';
import { fieldRegistry } from '../fields/registry';
import { RecordContext, usePage } from './context';
import { Action, isAction, type ActionProps } from './Action';
import type { FieldDescriptor } from '../../types';

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

/** Flatten fields, descending into groups. */
function collectFields(nodes: React.ReactNode): React.ReactElement<FormFieldProps>[] {
  const out: React.ReactElement<FormFieldProps>[] = [];
  for (const node of React.Children.toArray(nodes)) {
    if (isFormField(node)) {
      out.push(node);
    } else if (isFormGroup(node)) {
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

  const [values, setValues] = React.useState<Record<string, unknown>>({});
  const [types, setTypes] = React.useState<Record<string, string>>({});
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [activeAction, setActiveAction] = React.useState<React.ReactElement<ActionProps> | null>(null);

  React.useEffect(() => {
    if (!active || !modelName) {
      return;
    }
    let cancelled = false;

    void (async () => {
      try {
        const schema = await model(modelName).call<FieldDescriptor[]>('fields');
        if (!cancelled) {
          const map: Record<string, string> = {};
          for (const descriptor of schema) {
            map[descriptor.name] = descriptor.ttype;
          }
          setTypes(map);
        }
      } catch {
        // ignore: fall back to defaults
      }

      if (editing) {
        try {
          const record = await model(modelName).find<Record<string, unknown>>(
            recordId as number,
          );
          if (!cancelled) {
            setValues(record ?? {});
          }
        } catch {
          // ignore
        }
      } else if (!cancelled) {
        setValues({});
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [active, modelName, recordId, editing]);

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
    setBusy(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {};
      for (const field of fields) {
        payload[field.props.name] = values[field.props.name];
      }
      if (editing) {
        await model(modelName).update(recordId as number, payload);
      } else {
        await model(modelName).create(payload);
      }
      saved();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const renderField = (field: React.ReactElement<FormFieldProps>, key: React.Key) => {
    const name = field.props.name;
    const label = field.props.label ?? name;
    const ttype = field.props.ttype ?? types[name] ?? 'char';
    const Widget = fieldRegistry.get(ttype) ?? fieldRegistry.get('char');
    return (
      <label key={key} className="block">
        <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
        {Widget ? (
          <Widget
            field={{ name, label, ttype, readonly: isReadonly }}
            value={values[name]}
            readonly={isReadonly}
            onChange={(value) => setValues((state) => ({ ...state, [name]: value }))}
          />
        ) : null}
      </label>
    );
  };

  const renderNodes = (nodes: React.ReactNode): React.ReactNode =>
    React.Children.toArray(nodes).map((node, index) => {
      if (isAction(node)) {
        return null; // actions are shown in the ⋯ menu
      }
      if (isFormField(node)) {
        return renderField(node, index);
      }
      if (isFormGroup(node)) {
        return (
          <fieldset
            key={index}
            className="rounded-lg border border-slate-200 p-4 md:col-span-2"
          >
            {node.props.label ? (
              <legend className="px-1 text-sm font-medium text-slate-600">
                {node.props.label}
              </legend>
            ) : null}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {renderNodes(node.props.children)}
            </div>
          </fieldset>
        );
      }
      return (
        <div key={index} className="md:col-span-2">
          {node}
        </div>
      );
    });

  return (
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
                className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
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

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {renderNodes(children)}
        </div>
      </div>

      {activeAction
        ? React.cloneElement(activeAction, {
            open: true,
            onClose: () => setActiveAction(null),
          })
        : null}
    </RecordContext.Provider>
  );
}
