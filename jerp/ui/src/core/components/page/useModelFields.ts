import * as React from 'react';

import { model } from '../../model';
import type { FieldDescriptor } from '../../types';

/** Fields supplied by the framework; never auto-rendered. */
const AUTO_EXCLUDED = new Set(['id', 'created_at', 'updated_at']);

/**
 * Loads a model's field schema. Used to append fields contributed by modules
 * (``_inherit`` / ``_inherits``) without editing the owning module's view.
 */
export function useModelFields(modelName?: string): FieldDescriptor[] {
  const [fields, setFields] = React.useState<FieldDescriptor[]>([]);

  React.useEffect(() => {
    if (!modelName) {
      setFields([]);
      return;
    }

    let cancelled = false;
    void (async () => {
      try {
        const schema = await model(modelName).call<FieldDescriptor[]>('fields');
        if (!cancelled) {
          setFields(schema);
        }
      } catch {
        if (!cancelled) {
          setFields([]);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [modelName]);

  return fields;
}

/** Fields added by module extensions that were not explicitly declared. */
export function autoModelFields(
  schema: FieldDescriptor[],
  explicitNames: Set<string>,
): FieldDescriptor[] {
  return schema.filter(
    (field) =>
      Boolean(field.extension) &&
      !AUTO_EXCLUDED.has(field.name) &&
      !field.hide &&
      !explicitNames.has(field.name),
  );
}

/**
 * Resolves many2one ids to display labels, keyed by related model name.
 * Tables and cards use this so relation columns show names instead of ids.
 */
export function useRelationLabels(
  schema: FieldDescriptor[],
): Record<string, Record<string, string>> {
  const [labels, setLabels] = React.useState<Record<string, Record<string, string>>>({});

  const relations = React.useMemo(
    () =>
      Array.from(
        new Set(
          schema
            .map((field) => field.relation)
            .filter((relation): relation is string => Boolean(relation)),
        ),
      ),
    [schema],
  );
  const relationKey = relations.join(',');

  React.useEffect(() => {
    if (relations.length === 0) {
      setLabels({});
      return;
    }

    let cancelled = false;
    void (async () => {
      const next: Record<string, Record<string, string>> = {};
      for (const relation of relations) {
        try {
          const rows = await model(relation).all<Record<string, unknown>>({
            limit: 1000,
          });
          const map: Record<string, string> = {};
          for (const row of rows) {
            map[String(row.id)] = String(row._label ?? row.name ?? `#${row.id}`);
          }
          next[relation] = map;
        } catch {
          next[relation] = {};
        }
      }
      if (!cancelled) {
        setLabels(next);
      }
    })();

    return () => {
      cancelled = true;
    };
    // ``relations`` is derived from the schema; the key keeps the effect stable.
  }, [relationKey]);

  return labels;
}
