import * as React from 'react';

import { model } from '../../model';
import type { DraftRecord } from '../../model';
import { DraftContext } from '../page/context';
import type { FieldProps } from './registry';
import { StringField } from './StringField';

interface Option {
  id: number | string;
  _label?: string;
  name?: string;
}

/** Select widget for ``Many2oneField`` relations, including drafts. */
export function Many2oneField({ field, value, onChange, readonly }: FieldProps) {
  const relation = field.relation ?? null;
  const draftContext = React.useContext(DraftContext);
  const token = draftContext?.token;
  const draftsVersion = draftContext?.draftsVersion ?? 0;
  const [options, setOptions] = React.useState<Option[]>([]);
  const [drafts, setDrafts] = React.useState<DraftRecord[]>([]);

  React.useEffect(() => {
    if (!relation) {
      setOptions([]);
      return;
    }

    let cancelled = false;
    void (async () => {
      try {
        const rows = await model(relation).all<Option>({ limit: 200 });
        if (!cancelled) {
          setOptions(rows);
        }
      } catch {
        if (!cancelled) {
          setOptions([]);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [relation]);

  React.useEffect(() => {
    if (!relation || !token) {
      setDrafts([]);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const rows = await model(relation).drafts(token);
        if (!cancelled) {
          setDrafts(
            rows.filter(
              (draft) =>
                draft.model === relation &&
                draft.state !== 'delete' &&
                draft.id !== draftContext?.draftId,
            ),
          );
        }
      } catch {
        if (!cancelled) {
          setDrafts([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [relation, token, draftsVersion, draftContext?.draftId]);

  if (!relation) {
    return (
      <StringField
        field={field}
        value={value}
        onChange={onChange}
        readonly={readonly}
      />
    );
  }

  const current = value === null || value === undefined ? '' : String(value);
  const draftRecordIds = new Set(
    drafts
      .map((draft) => draft.record_id)
      .filter((id): id is number => id !== null && id !== undefined)
      .map(String),
  );
  const realOptions = options.filter(
    (option) => !draftRecordIds.has(String(option.id)),
  );
  const known =
    realOptions.some((option) => String(option.id) === current) ||
    drafts.some((draft) => `draft:${draft.id}` === current);

  return (
    <select
      className="w-full rounded border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30 disabled:bg-slate-100"
      value={current}
      disabled={readonly}
      onChange={(event) => {
        const next = event.target.value;
        if (next === '') {
          onChange(null);
        } else if (next.startsWith('draft:')) {
          onChange(next);
        } else {
          onChange(Number(next));
        }
      }}
    >
      <option value="">-</option>
      {!known && current ? <option value={current}>#{current}</option> : null}
      {drafts.length > 0 ? (
        <optgroup label="Drafts">
          {drafts.map((draft) => {
            const label =
              String(
                draft.values.name ??
                  draft.values._label ??
                  `#${draft.id}`,
              );
            return (
              <option key={`draft-${draft.id}`} value={`draft:${draft.id}`}>
                {label} (draft)
              </option>
            );
          })}
        </optgroup>
      ) : null}
      {realOptions.map((option) => (
        <option key={String(option.id)} value={String(option.id)}>
          {option._label ?? option.name ?? `#${option.id}`}
        </option>
      ))}
    </select>
  );
}
