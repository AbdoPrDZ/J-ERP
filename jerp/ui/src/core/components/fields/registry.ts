import type { ComponentType } from 'react';

import type { FieldDescriptor } from '../../types';

export interface FieldProps {
  field: FieldDescriptor;
  value: unknown;
  onChange: (value: unknown) => void;
  readonly?: boolean;
  error?: string;
}

export type FieldComponent = ComponentType<FieldProps>;

class FieldRegistry {
  private widgets = new Map<string, FieldComponent>();

  register(ttype: string, widget: FieldComponent): void {
    this.widgets.set(ttype, widget);
  }

  get(ttype: string): FieldComponent | undefined {
    return this.widgets.get(ttype);
  }

  keys(): string[] {
    return [...this.widgets.keys()];
  }
}

export const fieldRegistry = new FieldRegistry();
