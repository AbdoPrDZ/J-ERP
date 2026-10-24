import * as React from 'react';

import type { DataClient } from '../../model';
import { Action, ActionContent, ActionFooter, ActionHeader } from './Action';

/** A table action that opens a schema plan before it is applied. */
export interface PlanRequest {
  client: DataClient;
  /** Model API method applied on confirmation (e.g. ``update``). */
  method: string;
  /** Model API method returning the plan (e.g. ``preview``). */
  preview: string;
  /** Whether the action offers the database-wide drop option. */
  allowDrop: boolean;
  /** Record key holding the target (e.g. the module name). */
  field: string;
  value: unknown;
  /** Button label, used in the dialog title. */
  label: string;
}

interface PlanChange {
  op: string;
  table?: string;
  column?: string;
  field?: string;
  index?: string;
  old?: string;
  reason?: string;
  required?: boolean;
  nullable?: boolean;
  unique?: boolean;
  from?: string;
  to?: string;
}

interface Plan {
  changes?: PlanChange[];
  blocked?: PlanChange[];
  warnings?: string[];
  destructive?: boolean;
}

function describe(change: PlanChange): string {
  const target = [change.table, change.column].filter(Boolean).join('.');
  switch (change.op) {
    case 'create_table':
      return `create table ${change.table ?? ''}`;
    case 'rename_table':
      return `rename table ${change.old} → ${change.table}`;
    case 'rename_column':
      return `rename ${target} (from ${change.old})`;
    case 'alter_type':
      return `retype ${target} (${change.from} → ${change.to})`;
    case 'add_column':
      return `add ${target}${change.required ? ' (required)' : ''}`;
    case 'set_nullable':
      return `set ${target} ${change.nullable ? 'nullable' : 'not null'}`;
    case 'retire_column':
      return `retire ${target} (column kept)`;
    case 'drop_column':
      return `drop ${target} (permanent)`;
    case 'create_index':
      return `index ${change.index}${change.unique ? ' (unique)' : ''}`;
    case 'rename_index':
      return `rename index ${change.old} → ${change.index}`;
    case 'drop_index':
      return `drop index ${change.index ?? ''}`;
    default:
      return `${change.op} ${target}`.trim();
  }
}

function PlanList({
  changes,
  tone,
}: {
  changes: PlanChange[];
  tone: 'neutral' | 'danger';
}) {
  return (
    <ul
      className={`space-y-1 rounded border px-3 py-2 font-mono text-xs ${
        tone === 'danger'
          ? 'border-red-200 bg-red-50 text-red-700'
          : 'border-slate-200 bg-slate-50 text-slate-700'
      }`}
    >
      {changes.map((change, index) => (
        <li key={`${change.op}-${index}`} className="break-words">
          {describe(change)}
          {change.reason ? (
            <span className="ml-1 font-sans text-red-600">
              — {change.reason}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export interface PlanDialogProps {
  request: PlanRequest | null;
  onClose: () => void;
  onApplied: () => void | Promise<void>;
}

/** Shows a schema plan and applies the action when the user confirms it. */
export function PlanDialog({ request, onClose, onApplied }: PlanDialogProps) {
  const [allowDrop, setAllowDrop] = React.useState(false);
  const [plan, setPlan] = React.useState<Plan | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [applying, setApplying] = React.useState(false);
  const [confirmed, setConfirmed] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setPlan(null);
    setError(null);
    setConfirmed(false);
    setApplying(false);
    if (!request) {
      setAllowDrop(false);
      return;
    }
    setAllowDrop(request.allowDrop);
  }, [request]);

  React.useEffect(() => {
    if (!request) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = request.allowDrop
      ? { [request.field]: request.value, allow_drop: allowDrop }
      : { [request.field]: request.value };
    request.client
      .call<Plan>(request.preview, params)
      .then((value) => {
        if (!cancelled) {
          setPlan(value);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setPlan(null);
          setError((err as Error).message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [request, allowDrop]);

  const apply = async () => {
    if (!request || applying) {
      return;
    }
    setApplying(true);
    setError(null);
    const params = request.allowDrop
      ? { [request.field]: request.value, allow_drop: allowDrop }
      : { [request.field]: request.value };
    try {
      const result = await request.client.call<{
        plan?: Plan;
        error?: string;
      }>(request.method, params);
      if (result?.plan) {
        setPlan(result.plan);
      }
      if (result?.error) {
        setError(result.error);
        return;
      }
      await onApplied();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setApplying(false);
    }
  };

  const changes = plan?.changes ?? [];
  const blocked = plan?.blocked ?? [];
  const warnings = plan?.warnings ?? [];
  const destructive = Boolean(plan?.destructive);

  return (
    <Action
      label="Schema plan"
      open={Boolean(request)}
      onClose={applying ? undefined : onClose}
    >
      <ActionHeader>Review schema changes</ActionHeader>
      <ActionContent>
        <p className="text-sm text-slate-600">
          Updating{' '}
          <span className="font-medium text-brand-navy">
            {request?.label ?? 'the module'}
          </span>{' '}
          synchronizes the database schema. Nothing is changed until you apply.
        </p>

        {loading ? <p className="text-sm text-slate-500">Loading plan…</p> : null}

        {error ? (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {plan && !loading ? (
          <>
            {changes.length > 0 ? (
              <PlanList changes={changes} tone="neutral" />
            ) : (
              <p className="text-sm text-slate-500">No schema changes.</p>
            )}

            {blocked.length > 0 ? (
              <div className="space-y-1">
                <p className="text-sm font-medium text-red-700">
                  Blocked ({blocked.length}) — these will be skipped:
                </p>
                <PlanList changes={blocked} tone="danger" />
              </div>
            ) : null}

            {warnings.length > 0 ? (
              <ul className="space-y-1 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                {warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : null}

            {request?.allowDrop ? (
              <label className="flex items-start gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4"
                  checked={allowDrop}
                  disabled={applying}
                  onChange={(event) => setAllowDrop(event.target.checked)}
                />
                <span>
                  Drop retired columns for the whole database. Columns are
                  currently kept; dropping them permanently deletes their data.
                </span>
              </label>
            ) : null}

            {destructive ? (
              <label className="flex items-start gap-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4"
                  checked={confirmed}
                  disabled={applying}
                  onChange={(event) => setConfirmed(event.target.checked)}
                />
                <span>
                  I understand the columns listed above will be permanently
                  deleted.
                </span>
              </label>
            ) : null}
          </>
        ) : null}
      </ActionContent>
      <ActionFooter>
        <button
          type="button"
          className="rounded border border-slate-300 px-3 py-1 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-40"
          disabled={applying}
          onClick={onClose}
        >
          Cancel
        </button>
        <button
          type="button"
          className="rounded bg-brand-blue px-3 py-1 text-sm font-medium text-white hover:bg-brand-blue-dark disabled:opacity-40"
          disabled={loading || applying || !plan || (destructive && !confirmed)}
          onClick={() => void apply()}
        >
          {applying ? 'Applying…' : 'Apply'}
        </button>
      </ActionFooter>
    </Action>
  );
}
