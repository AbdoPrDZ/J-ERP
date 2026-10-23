import type { ComponentType } from 'react';

import type { StandardViewProps } from '../../types';

/** Maps a standard view type (form/table/cards) to its component. */
class ViewRegistry {
  private types = new Map<string, ComponentType<StandardViewProps>>();

  register(type: string, component: ComponentType<StandardViewProps>): void {
    this.types.set(type, component);
  }

  get(type: string): ComponentType<StandardViewProps> | undefined {
    return this.types.get(type);
  }

  keys(): string[] {
    return [...this.types.keys()];
  }
}

export const viewRegistry = new ViewRegistry();
