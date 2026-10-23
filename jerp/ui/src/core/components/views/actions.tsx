import type { ActionDescriptor, RecordType } from '../../types';

const STYLES: Record<string, string> = {
  primary: 'bg-brand-blue text-white hover:bg-brand-blue-dark',
  danger: 'border border-red-200 text-red-600 hover:bg-red-50',
  default: 'border border-slate-300 text-slate-700 hover:border-brand-cyan hover:bg-brand-cyan/5',
};

export function RecordActions({
  actions,
  record,
  onAction,
  busy,
}: {
  actions?: ActionDescriptor[];
  record: RecordType;
  onAction?: (action: ActionDescriptor, record: RecordType) => void;
  busy?: boolean;
}) {
  if (!actions || actions.length === 0) {
    return null;
  }
  return (
    <div className="flex justify-end gap-2">
      {actions.map((action) => (
        <button
          key={action.label}
          type="button"
          className={`rounded px-3 py-1 text-sm disabled:opacity-40 ${
            STYLES[action.style ?? 'default'] ?? STYLES.default
          }`}
          disabled={busy}
          onClick={() => onAction?.(action, record)}
        >
          {action.label}
        </button>
      ))}
    </div>
  );
}
