import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import type { ComponentType } from 'react';

import { App } from './App';
import type { ViewProps } from './types';

export interface ViewModule {
  default: ComponentType<ViewProps>;
}

export type ViewLoader = () => Promise<ViewModule>;

class ViewsRegistry {
  private loaders = new Map<string, ViewLoader>();
  private roots = new WeakMap<Element, Root>();

  register(key: string, loader: ViewLoader): void {
    this.loaders.set(key, loader);
  }

  has(key: string): boolean {
    return this.loaders.has(key);
  }

  keys(): string[] {
    return [...this.loaders.keys()];
  }

  async load(key: string): Promise<ViewModule> {
    const loader = this.loaders.get(key);
    if (!loader) {
      throw new Error(`View "${key}" is not registered.`);
    }
    return loader();
  }

  async mount(
    key: string,
    element: Element,
    context: Record<string, unknown> = {},
  ): Promise<void> {
    const module = await this.load(key);
    let root = this.roots.get(element);
    if (!root) {
      root = createRoot(element);
      this.roots.set(element, root);
    }
    root.render(<App viewKey={key} context={context} view={module.default} />);
  }
}

export const viewsRegistry = new ViewsRegistry();
export type { ViewsRegistry };
