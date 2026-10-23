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
}

export function model(name: string): ModelClient {
  return new ModelClient(name);
}
