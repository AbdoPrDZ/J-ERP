export interface FieldDescriptor {
  name: string;
  label: string;
  ttype: string;
  required?: boolean;
  readonly?: boolean;
  hide?: boolean;
  help?: string | null;
  extension?: boolean;
  size?: number;
  has_default?: boolean;
  selection?: [string, string][];
  relation?: string | null;
  multi_language?: boolean;
  default?: unknown;
}

export interface FormSchema {
  model?: string;
  fields: FieldDescriptor[];
}

export interface ViewProps {
  context: Record<string, unknown>;
}

export interface ActionDescriptor {
  label: string;
  endpoint: string;
  method?: string;
  style?: 'primary' | 'default' | 'danger';
  /** Record key sent to the endpoint (defaults to ``id``). */
  key?: string;
}

export interface ViewDescriptor {
  type: string;
  model?: string;
  title?: string;
  description?: string;
  fields: FieldDescriptor[];
  actions?: ActionDescriptor[];
}

export type RecordType = Record<string, unknown> & {
  id?: unknown;
  _actions?: ActionDescriptor[];
};

export interface StandardViewProps {
  view: ViewDescriptor;
  records: RecordType[];
  onAction?: (action: ActionDescriptor, record: RecordType) => void;
  busy?: boolean;
}
