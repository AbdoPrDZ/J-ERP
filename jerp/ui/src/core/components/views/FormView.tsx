import * as React from 'react';

import { Form } from '../form';
import type { StandardViewProps } from '../../types';

export function FormView({ view, records }: StandardViewProps) {
  const [values, setValues] = React.useState<Record<string, unknown>>(
    () => records[0] ?? {},
  );

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6">
      <Form
        schema={{ model: view.model, fields: view.fields }}
        values={values}
        onChange={(name, value) =>
          setValues((state) => ({ ...state, [name]: value }))
        }
      />
    </div>
  );
}
