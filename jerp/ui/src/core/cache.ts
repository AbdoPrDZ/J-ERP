import { model, type DataClient, type ListParams } from './model';

export interface CacheClient extends DataClient {
  commit(parentField: string, parentId: number | string): Promise<number>;
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

function sortRows(rows: Record<string, unknown>[], order?: string) {
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

/**
 * In-memory client for FormTable. Reads existing child records once, stages
 * creates/updates/deletes locally, and flushes everything when the parent form
 * is saved.
 */
export function cacheClient(
  modelName: string,
  relationField: string,
  parentId: number | string | null,
): CacheClient {
  let records: Record<string, unknown>[] = [];
  let loaded = false;
  let loading: Promise<void> | null = null;
  let nextId = -1;
  const deleted = new Set<string>();
  const dirty = new Map<string, Record<string, unknown>>();

  const load = async () => {
    if (loaded) {
      return;
    }
    if (!loading) {
      loading = (async () => {
        if (parentId !== null && parentId !== undefined && parentId !== '') {
          records = await model(modelName).all<Record<string, unknown>>({
            domain: [[relationField, '=', parentId]],
          });
        }
        loaded = true;
      })();
    }
    await loading;
  };

  const findIndex = (id: number | string) =>
    records.findIndex((record) => String(record.id) === String(id));

  const remove = async (id: number | string): Promise<boolean> => {
    await load();
    const index = findIndex(id);
    if (index < 0) {
      return false;
    }
    records = records.filter((_record, position) => position !== index);
    const key = String(id);
    dirty.delete(key);
    if (Number(id) > 0) {
      deleted.add(key);
    }
    return true;
  };

  return {
    async all<T = Record<string, unknown>>(params: ListParams = {}) {
      await load();
      let rows = [...records];
      rows = sortRows(rows, params.order);
      const offset = params.offset ?? 0;
      if (offset) {
        rows = rows.slice(offset);
      }
      if (params.limit !== undefined) {
        rows = rows.slice(0, params.limit);
      }
      return rows as T[];
    },

    async count() {
      await load();
      return records.length;
    },

    async find<T = Record<string, unknown>>(id: number | string) {
      await load();
      const index = findIndex(id);
      return (index >= 0 ? records[index] : null) as T | null;
    },

    async create<T = Record<string, unknown>>(values: Record<string, unknown>) {
      await load();
      const id = nextId;
      nextId -= 1;
      const record = { ...values, id };
      records = [record, ...records];
      return record as T;
    },

    async update<T = Record<string, unknown>>(
      id: number | string,
      values: Record<string, unknown>,
    ) {
      await load();
      const index = findIndex(id);
      if (index < 0) {
        throw new Error('Record not found.');
      }
      const record = { ...records[index], ...values };
      records[index] = record;
      if (Number(id) > 0) {
        dirty.set(String(id), {
          ...(dirty.get(String(id)) ?? {}),
          ...values,
        });
      }
      return record as T;
    },

    delete: remove,
    async deleteMany(ids: Array<number | string>) {
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
        return (await remove(params.id as number | string)) as T;
      }
      throw new Error(`Unsupported cached action "${func}".`);
    },

    async commit(parentField: string, newParentId: number | string) {
      await load();
      let changed = 0;
      for (const id of deleted) {
        if (await model(modelName).delete(id)) {
          changed += 1;
        }
      }
      for (const [id, values] of dirty) {
        await model(modelName).update(id, values);
        changed += 1;
      }
      for (const record of records) {
        if (Number(record.id) >= 0) {
          continue;
        }
        const payload = { ...record, [parentField]: newParentId };
        delete payload.id;
        delete payload._label;
        await model(modelName).create(payload);
        changed += 1;
      }
      records = records.filter((record) => Number(record.id) >= 0);
      deleted.clear();
      dirty.clear();
      return changed;
    },
  };
}
