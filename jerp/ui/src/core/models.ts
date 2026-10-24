import * as React from 'react';

import { api } from './api';

export type ModelViews = Record<string, string>;

interface ModelsPayload {
  models?: ModelViews;
}

/**
 * Load the models available to the global search from the server.
 *
 * This deliberately keeps no module-level cache: the search bar is mounted
 * when the drawer opens, so every opening performs a fresh, uncached request.
 */
export function useAvailableModels(): ModelViews {
  const [models, setModels] = React.useState<ModelViews>({});

  React.useEffect(() => {
    let cancelled = false;
    void api
      .getFresh<ModelsPayload>('/models')
      .then((payload) => {
        if (!cancelled) {
          setModels(payload?.models ?? {});
        }
      })
      .catch(() => {
        if (!cancelled) {
          setModels({});
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return models;
}
