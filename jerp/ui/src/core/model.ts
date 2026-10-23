import { api } from './api';

export interface ListParams {
  domain?: unknown[];
  fields?: string[];
  order?: string;
  limit?: number;
  offset?: number;
}

export interface DataClient {
  all<T = Record<string, unknown>>(params?: ListParams): Promise<T[]>;
  count(domain?: unknown[]): Promise<number>;
  find<T = Record<string, unknown>>(
    id: number | string,
    fields?: string[],
  ): Promise<T | null>;
  create<T = Record<string, unknown>>(
    values: Record<string, unknown>,
  ): Promise<T>;
  update<T = Record<string, unknown>>(
    id: number | string,
    values: Record<string, unknown>,
  ): Promise<T>;
  delete(id: number | string): Promise<boolean>;
  deleteMany(ids: Array<number | string>): Promise<number>;
  call<T = unknown>(
    func: string,
    params?: Record<string, unknown>,
  ): Promise<T>;
}

export interface DraftRecord {
  id: number;
  draft_id: number;
  model: string;
  record_id?: number | null;
  state: 'create' | 'update' | 'delete';
  values: Record<string, unknown>;
  dirty: Record<string, unknown>;
  version: number;
  base_stamp?: string | null;
}

export interface DraftChange extends DraftRecord {
  changed: string[];
  warnings: unknown[];
  errors: Record<string, string>;
  domains: Record<string, unknown>;
}

export interface DraftCommitResult {
  draft_id: number;
  model: string;
  id: number;
  state: string;
}

/**
 * Typed client for a model's API endpoint.
 *
 *   model('stock.product').all({ limit: 20 })
 *   model('stock.product').create({ name: 'Widget' })
 *   model('module').install({ name: 'stock' })   // call any exposed method
 */
export class ModelClient implements DataClient {
  constructor(private readonly name: string) {}

  /** Call any exposed method by name. */
  async call<T = unknown>(
    func: string,
    params: Record<string, unknown> = {},
  ): Promise<T> {
    const body = await api.post<{ result: T }>(
      `/model/${this.name}/${func}`,
      params,
    );
    return body.result;
  }

  all<T = Record<string, unknown>>(params: ListParams = {}): Promise<T[]> {
    return this.call<T[]>('all', params as Record<string, unknown>);
  }

  count(domain?: unknown[]): Promise<number> {
    return this.call<number>('count', domain ? { domain } : {});
  }

  find<T = Record<string, unknown>>(
    id: number | string,
    fields?: string[],
  ): Promise<T | null> {
    return this.call<T | null>('find', { id, fields });
  }

  create<T = Record<string, unknown>>(
    values: Record<string, unknown>,
  ): Promise<T> {
    return this.call<T>('create', values);
  }

  update<T = Record<string, unknown>>(
    id: number | string,
    values: Record<string, unknown>,
  ): Promise<T> {
    return this.call<T>('update', { id, values });
  }

  delete(id: number | string): Promise<boolean> {
    return this.call<boolean>('delete', { id });
  }

  deleteMany(ids: Array<number | string>): Promise<number> {
    return this.call<number>('delete_many', { ids });
  }

  newDraft(
    token?: string,
    values?: Record<string, unknown>,
    reuse = true,
  ): Promise<DraftRecord> {
    return this.call<DraftRecord>('new', { token, values, reuse });
  }

  editDraft(
    id: number | string,
    token?: string,
    values?: Record<string, unknown>,
  ): Promise<DraftRecord> {
    return this.call<DraftRecord>('edit', { id, token, values });
  }

  changeDraft(
    draftId: number | string,
    values: Record<string, unknown>,
  ): Promise<DraftChange> {
    return this.call<DraftChange>('change', { draft_id: draftId, values });
  }

  drafts(token: string): Promise<DraftRecord[]> {
    return this.call<DraftRecord[]>('drafts', { token });
  }

  discardDraft(draftId: number | string): Promise<boolean> {
    return this.call<boolean>('discard', { draft_id: draftId });
  }

  discardAllDrafts(token: string): Promise<number> {
    return this.call<number>('discard_all', { token });
  }

  removeDraft(
    token: string,
    id: number | string,
  ): Promise<DraftRecord | null> {
    return this.call<DraftRecord | null>('remove', { token, id });
  }

  commitDrafts(
    token: string,
    parentField?: string,
    parentId?: number | string,
  ): Promise<DraftCommitResult[]> {
    return this.call<DraftCommitResult[]>('commit', {
      token,
      parent_field: parentField,
      parent_id: parentId,
    });
  }
}

export function model(name: string): ModelClient {
  return new ModelClient(name);
}
