import { api } from './api';
import type { DataClient, ListParams } from './model';

export interface TempClient extends DataClient {
  commit(parentField: string, parentId: number | string): Promise<number>;
}

/** Client for temporary records grouped by one form token. */
export function tempClient(model: string, token: string): TempClient {
  const call = async <T>(
    func: string,
    params: Record<string, unknown> = {},
  ): Promise<T> => {
    const body = await api.post<{ result: T }>(`/temp/${model}/${func}`, {
      token,
      ...params,
    });
    return body.result;
  };

  return {
    all: <T = Record<string, unknown>>(params: ListParams = {}) =>
      call<T[]>('all', params as Record<string, unknown>),
    count: (domain?: unknown[]) =>
      call<number>('count', domain ? { domain } : {}),
    find: <T = Record<string, unknown>>(id: number | string) =>
      call<T | null>('find', { id }),
    create: <T = Record<string, unknown>>(values: Record<string, unknown>) =>
      call<T>('create', { values }),
    update: <T = Record<string, unknown>>(
      id: number | string,
      values: Record<string, unknown>,
    ) => call<T>('update', { id, values }),
    delete: (id: number | string) => call<boolean>('delete', { id }),
    deleteMany: (ids: Array<number | string>) =>
      call<number>('delete_many', { ids }),
    call,
    commit: (parentField: string, parentId: number | string) =>
      call<number>('commit', {
        parent_field: parentField,
        parent_id: parentId,
      }),
  };
}
