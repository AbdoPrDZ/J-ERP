import { api } from './api';

export interface ListParams {
  domain?: unknown[];
  fields?: string[];
  order?: string;
  limit?: number;
  offset?: number;
}

/**
 * Typed client for a model's API endpoint.
 *
 *   model('product').all({ limit: 20 })
 *   model('product').create({ name: 'Widget' })
 *   model('module').install({ name: 'stock' })   // call any exposed method
 */
export class ModelClient {
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
}

export function model(name: string): ModelClient {
  return new ModelClient(name);
}
