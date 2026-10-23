import * as React from 'react';

import { model } from '../../model';
import type { FieldDescriptor } from '../../types';

interface Language {
  id: number;
  name: string;
  code: string;
  is_default?: boolean;
  active?: boolean;
}

interface MultiLangPanelProps {
  field: FieldDescriptor;
  defaultValue?: string;
  modelName?: string;
  recordId?: number | string | null;
  readonly?: boolean;
}

/** Compact button + modal showing every language value of a field. */
export function MultiLangPanel({
  field,
  defaultValue,
  modelName,
  recordId,
  readonly,
}: MultiLangPanelProps) {
  const [open, setOpen] = React.useState(false);
  const [languages, setLanguages] = React.useState<Language[]>([]);
  const [values, setValues] = React.useState<Record<string, string>>({});
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const rows = await model('sys.lang').all<Language>({
          domain: [['active', '=', true]],
          order: 'id',
        });
        if (!cancelled) {
          setLanguages(rows);
        }
      } catch {
        if (!cancelled) {
          setLanguages([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    if (!modelName || !recordId) {
      setValues({});
      return;
    }

    let cancelled = false;
    void (async () => {
      try {
        const result = await model(modelName).call<Record<string, string>>(
          'translations',
          { id: recordId, field: field.name },
        );
        if (!cancelled) {
          setValues(result ?? {});
        }
      } catch {
        if (!cancelled) {
          setValues({});
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [modelName, recordId, field.name]);

  React.useEffect(() => {
    if (!open) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open]);

  if (!modelName) {
    return null;
  }

  const setValue = (code: string, value: string) =>
    setValues((state) => ({ ...state, [code]: value }));

  const save = async (code: string, value: string) => {
    if (!modelName || !recordId || readonly) {
      return;
    }
    setBusy(code);
    setError(null);
    try {
      await model(modelName).call('set_translation', {
        id: recordId,
        field: field.name,
        lang: code,
        value,
      });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const defaultLanguage =
    languages.find((language) => language.is_default) ?? languages[0];
  const orderedLanguages = [...languages].sort(
    (a, b) => Number(Boolean(b.is_default)) - Number(Boolean(a.is_default)),
  );
  const title = field.label ?? field.name;

  return (
    <>
      <button
        type="button"
        aria-label={`${title} translations`}
        title={`${title} translations`}
        className="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full text-base text-slate-500 hover:bg-brand-cyan/10 hover:text-brand-blue"
        onClick={() => setOpen(true)}
      >
        🌐
      </button>

      {open ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-brand-navy/60 p-4"
          onClick={() => setOpen(false)}
          role="presentation"
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label={`${title} translations`}
            className="max-h-[80vh] w-full max-w-lg overflow-hidden rounded-lg bg-white shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
              <h3 className="text-base font-semibold">{title} translations</h3>
              <button
                type="button"
                aria-label="Close"
                className="rounded px-2 text-slate-400 hover:bg-brand-cyan/10 hover:text-brand-blue"
                onClick={() => setOpen(false)}
              >
                ✕
              </button>
            </div>

            <div className="max-h-[60vh] space-y-3 overflow-y-auto px-5 py-4">
              {!recordId ? (
                <p className="text-xs text-slate-500">
                  Save the record first to edit translations.
                </p>
              ) : null}

              {error ? <p className="text-xs text-red-600">{error}</p> : null}

              {orderedLanguages.length === 0 ? (
                <p className="text-xs text-slate-500">No languages configured.</p>
              ) : null}

              {orderedLanguages.map((language) => {
                const isDefault = language.id === defaultLanguage?.id;
                const disabled = readonly || isDefault || !recordId;
                return (
                  <div key={language.code}>
                    <span className="mb-1 block text-xs text-slate-500">
                      {language.name} ({language.code})
                      {isDefault ? ' — default' : ''}
                    </span>
                    <input
                      type="text"
                      className="w-full rounded border border-slate-300 px-3 py-1.5 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30 disabled:bg-slate-100"
                      value={
                        isDefault
                          ? defaultValue ?? ''
                          : values[language.code] ?? ''
                      }
                      readOnly={disabled}
                      disabled={disabled || busy === language.code}
                      onChange={(event) =>
                        setValue(language.code, event.target.value)
                      }
                      onBlur={() =>
                        void save(language.code, values[language.code] ?? '')
                      }
                    />
                  </div>
                );
              })}
            </div>

            <div className="flex justify-end border-t border-slate-200 px-5 py-3">
              <button
                type="button"
                className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:border-brand-cyan hover:bg-brand-cyan/5"
                onClick={() => setOpen(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
