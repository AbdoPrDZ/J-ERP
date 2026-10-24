import * as React from 'react';
import { api } from '@jerp/ui';

interface DatabasesResponse {
  databases: string[];
  active: string | null;
  error: string | null;
}

const emptyForm = {
  name: '',
  adminLogin: 'admin',
  adminPassword: '',
  masterKey: '',
};

function initials(name: string): string {
  const letters = name.replace(/[^a-zA-Z0-9]/g, '').slice(0, 2);
  return letters ? letters.toUpperCase() : 'DB';
}

function Stat({
  label,
  value,
  tone = 'default',
  mono = false,
}: {
  label: string;
  value: string;
  tone?: 'default' | 'ok' | 'warn';
  mono?: boolean;
}) {
  const valueClass =
    tone === 'ok'
      ? 'text-emerald-600'
      : tone === 'warn'
        ? 'text-amber-600'
        : 'text-brand-navy';
  return (
    <div className="rounded-xl border border-slate-200 bg-white/80 px-4 py-3 shadow-sm backdrop-blur">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
        {label}
      </p>
      <p
        className={`mt-1 truncate text-sm font-semibold ${valueClass} ${
          mono ? 'font-mono' : ''
        }`}
      >
        {value}
      </p>
    </div>
  );
}

export default function DbManager() {
  const [data, setData] = React.useState<DatabasesResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [creating, setCreating] = React.useState(false);
  const [deleting, setDeleting] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setError(null);
    try {
      const result = await api.get<DatabasesResponse>('/databases');
      setData(result);
      if (result.error) {
        setError(result.error);
      }
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  const select = async (database: string) => {
    if (busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post('/databases/select', { name: database });
      window.location.assign('/login');
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  const databases = data?.databases ?? [];
  const active = data?.active ?? null;

  return (
    <div className="relative min-h-[calc(100dvh-1.5rem)] overflow-hidden rounded-2xl bg-brand-white">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(52rem 32rem at 5% 0%, rgba(34, 211, 238, 0.14), transparent 55%), radial-gradient(44rem 28rem at 100% 100%, rgba(37, 99, 235, 0.12), transparent 55%)',
        }}
      />

      <div className="relative mx-auto flex min-h-[calc(100dvh-1.5rem)] w-full max-w-5xl flex-col gap-8 px-4 py-8 sm:px-8 sm:py-10">
        <header className="flex flex-wrap items-start justify-between gap-5">
          <div className="flex items-center gap-4">
            <img
              src="/__assets/core/logo-full.png"
              alt="J-ERP — Modular ERP Framework"
              className="h-auto w-32 sm:w-40"
            />
            <div className="hidden h-10 w-px bg-slate-200 sm:block" />
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-brand-cyan-dark">
                Workspace
              </p>
              <h1 className="text-2xl font-semibold tracking-tight text-brand-navy">
                Databases
              </h1>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="rounded-lg border border-slate-300 bg-white/80 px-3 py-2 text-sm font-medium text-slate-600 transition hover:border-brand-cyan hover:bg-white hover:text-brand-navy"
              onClick={() => void load()}
            >
              Refresh
            </button>
            <button
              type="button"
              className="rounded-lg bg-brand-blue px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-blue-dark"
              onClick={() => setCreating(true)}
            >
              <span className="mr-1.5 text-base leading-none">+</span>
              New database
            </button>
          </div>
        </header>

        <div>
          <p className="max-w-2xl text-sm leading-relaxed text-slate-500">
            Choose an isolated workspace to sign in, or create a new one. Modules,
            data and users are kept separate per database.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <Stat label="Databases" value={String(databases.length)} />
          <Stat label="Active" value={active ?? 'None'} mono />
          <Stat
            label="Server"
            value={error ? 'Attention needed' : 'Connected'}
            tone={error ? 'warn' : 'ok'}
          />
        </div>

        {error ? (
          <div
            role="alert"
            className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            <span className="mt-0.5 flex h-5 w-5 flex-none items-center justify-center rounded-full bg-red-100 text-xs font-bold">
              !
            </span>
            <span>{error}</span>
          </div>
        ) : null}

        <section className="space-y-3">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold text-brand-navy">
                Available databases
              </h2>
              <p className="text-xs text-slate-400">
                Select a card to continue, or remove a workspace you no longer need.
              </p>
            </div>
            <span className="text-xs text-slate-400">
              {databases.length} total
            </span>
          </div>

          <div className="space-y-3">
            {data === null && !error ? (
              <div className="rounded-xl border border-slate-200 bg-white/80 px-5 py-8 text-center text-sm text-slate-400 shadow-sm">
                Loading databases…
              </div>
            ) : null}

            {databases.map((database) => {
              const isActive = database === active;
              return (
                <div
                  key={database}
                  role="button"
                  tabIndex={busy ? -1 : 0}
                  aria-busy={busy}
                  aria-label={`Open database ${database}`}
                  aria-current={isActive ? 'true' : undefined}
                  className={`flex cursor-pointer flex-wrap items-center gap-4 rounded-xl border bg-white p-4 shadow-sm transition focus:outline-none focus-visible:ring-4 focus-visible:ring-brand-cyan/30 ${
                    isActive
                      ? 'border-brand-cyan/70 ring-4 ring-brand-cyan/10'
                      : 'border-slate-200 hover:border-brand-cyan/50 hover:shadow-md'
                  } ${busy ? 'pointer-events-none opacity-60' : ''}`}
                  onClick={() => void select(database)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      void select(database);
                    }
                  }}
                >
                  <div
                    className={`flex h-11 w-11 flex-none items-center justify-center rounded-lg text-sm font-semibold ${
                      isActive
                        ? 'bg-brand-cyan/15 text-brand-cyan-dark'
                        : 'bg-brand-blue/10 text-brand-blue'
                    }`}
                  >
                    {initials(database)}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate font-mono text-sm font-medium text-brand-navy">
                        {database}
                      </p>
                      {isActive ? (
                        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 ring-1 ring-emerald-200">
                          Active
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-xs text-slate-400">
                      {isActive
                        ? 'Currently selected — click to sign in.'
                        : 'Click to select this workspace and sign in.'}
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-500 transition hover:border-red-200 hover:bg-red-50 hover:text-red-600 disabled:opacity-40"
                      disabled={busy}
                      onClick={(event) => {
                        event.stopPropagation();
                        setDeleting(database);
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              );
            })}

            {data !== null && databases.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 bg-white/60 px-6 py-10 text-center">
                <p className="text-sm font-semibold text-brand-navy">
                  No databases yet
                </p>
                <p className="mt-1 text-sm text-slate-500">
                  Create your first workspace to get started.
                </p>
                <button
                  type="button"
                  className="mt-5 rounded-lg bg-brand-blue px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-blue-dark"
                  onClick={() => setCreating(true)}
                >
                  Create database
                </button>
              </div>
            ) : null}
          </div>
        </section>

        <p className="mt-auto pt-2 text-center text-xs text-slate-400">
          J-ERP · Modular ERP Framework
        </p>
      </div>

      {creating ? (
        <CreateDatabaseModal
          onClose={() => setCreating(false)}
          onCreated={() => window.location.assign('/login')}
        />
      ) : null}

      {deleting ? (
        <DeleteDatabaseModal
          database={deleting}
          active={deleting === active}
          onClose={() => setDeleting(null)}
          onDeleted={(wasActive) => {
            setDeleting(null);
            if (wasActive) {
              window.location.assign('/db/manager');
              return;
            }
            void load();
          }}
        />
      ) : null}
    </div>
  );
}

interface DeleteModalProps {
  database: string;
  active: boolean;
  onClose: () => void;
  onDeleted: (wasActive: boolean) => void;
}

function ModalShell({
  tone,
  title,
  subtitle,
  children,
}: {
  tone: 'blue' | 'red';
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-50 flex items-center justify-center bg-brand-navy/60 p-4 backdrop-blur-sm"
    >
      <div className="max-h-[calc(100dvh-2rem)] w-full max-w-md overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-center gap-3 border-b border-slate-100 px-6 py-5">
          <div
            className={`flex h-9 w-9 flex-none items-center justify-center rounded-full text-base font-bold ${
              tone === 'red'
                ? 'bg-red-50 text-red-600'
                : 'bg-brand-blue/10 text-brand-blue'
            }`}
          >
            {tone === 'red' ? '!' : '+'}
          </div>
          <div>
            <h3 className="text-base font-semibold text-brand-navy">{title}</h3>
            <p className="text-xs text-slate-400">{subtitle}</p>
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}

function DeleteDatabaseModal({
  database,
  active,
  onClose,
  onDeleted,
}: DeleteModalProps) {
  const [confirm, setConfirm] = React.useState('');
  const [masterKey, setMasterKey] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (confirm !== database) {
      setError(`Type "${database}" to confirm deletion.`);
      return;
    }
    if (!masterKey) {
      setError('The master key is required.');
      return;
    }
    if (busy) {
      return;
    }

    setBusy(true);
    setError(null);
    try {
      await api.post('/databases/delete', {
        name: database,
        confirm,
        master_key: masterKey,
      });
      onDeleted(active);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <ModalShell
      tone="red"
      title="Delete database"
      subtitle="This action cannot be undone."
    >
      <form className="space-y-4 px-6 py-5" onSubmit={submit}>
        <p className="text-sm leading-relaxed text-slate-600">
          This permanently deletes{' '}
          <span className="whitespace-pre font-mono font-medium text-brand-navy">
            {database}
          </span>
          , including every module, table and record in it.
        </p>

        {active ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            This is the active database. You will be returned to the database
            manager after it is deleted.
          </div>
        ) : null}

        {error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">
            Type{' '}
            <span className="whitespace-pre font-mono">{database}</span> to confirm
          </span>
          <input
            autoFocus
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 font-mono text-sm text-brand-navy shadow-sm focus:border-red-500 focus:outline-none focus:ring-4 focus:ring-red-500/10"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
          />
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">
            Master key
          </span>
          <input
            type="password"
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm text-brand-navy shadow-sm focus:border-red-500 focus:outline-none focus:ring-4 focus:ring-red-500/10"
            value={masterKey}
            onChange={(event) => setMasterKey(event.target.value)}
          />
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-brand-cyan hover:bg-brand-cyan/5"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-40"
            disabled={busy || confirm !== database || !masterKey}
          >
            {busy ? 'Deleting…' : 'Delete database'}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

interface CreateModalProps {
  onClose: () => void;
  onCreated: () => void;
}

function CreateDatabaseModal({ onClose, onCreated }: CreateModalProps) {
  const [form, setForm] = React.useState(emptyForm);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const set = (key: keyof typeof emptyForm) => (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => setForm((state) => ({ ...state, [key]: event.target.value }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const name = form.name;
    if (!name.trim() || !form.adminPassword || !form.masterKey || busy) {
      setError(
        !name.trim()
          ? 'A database name is required.'
          : !form.adminPassword
            ? 'An admin password is required.'
            : 'The master key is required.',
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post('/databases', {
        name,
        admin_login: form.adminLogin.trim() || 'admin',
        admin_password: form.adminPassword,
        master_key: form.masterKey,
      });
      await api.post('/databases/select', { name });
      onCreated();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <ModalShell
      tone="blue"
      title="Create database"
      subtitle="A new isolated workspace."
    >
      <form className="space-y-4 px-6 py-5" onSubmit={submit}>
        {error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">
            Database name
          </span>
          <input
            autoFocus
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm text-brand-navy shadow-sm focus:border-brand-blue focus:outline-none focus:ring-4 focus:ring-brand-cyan/20"
            placeholder="name"
            value={form.name}
            onChange={set('name')}
          />
          <span className="mt-1 block text-xs text-slate-400">
            Case and spaces are preserved. Up to 63 bytes.
          </span>
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">
            Admin username
          </span>
          <input
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm text-brand-navy shadow-sm focus:border-brand-blue focus:outline-none focus:ring-4 focus:ring-brand-cyan/20"
            value={form.adminLogin}
            onChange={set('adminLogin')}
          />
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">
            Admin password
          </span>
          <input
            type="password"
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm text-brand-navy shadow-sm focus:border-brand-blue focus:outline-none focus:ring-4 focus:ring-brand-cyan/20"
            value={form.adminPassword}
            onChange={set('adminPassword')}
          />
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">
            Master key
          </span>
          <input
            type="password"
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm text-brand-navy shadow-sm focus:border-brand-blue focus:outline-none focus:ring-4 focus:ring-brand-cyan/20"
            value={form.masterKey}
            onChange={set('masterKey')}
          />
          <span className="mt-1 block text-xs text-slate-400">
            Required to create or delete databases.
          </span>
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-brand-cyan hover:bg-brand-cyan/5"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="rounded-lg bg-brand-blue px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-blue-dark disabled:cursor-not-allowed disabled:opacity-40"
            disabled={busy}
          >
            {busy ? 'Creating…' : 'Create database'}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}
