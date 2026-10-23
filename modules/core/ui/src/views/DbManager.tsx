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

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <img src="/__assets/core/logo.png" alt="J-ERP" className="h-9 w-9 rounded" />
        <div className="flex-1">
          <h2 className="text-xl font-semibold">Databases</h2>
          <p className="text-sm text-slate-500">
            Active:{' '}
            <span className="font-medium text-slate-700">{data?.active ?? 'none'}</span>
          </p>
        </div>
        <button
          type="button"
          className="rounded bg-brand-blue px-4 py-2 text-sm font-medium text-white hover:bg-brand-blue-dark"
          onClick={() => setCreating(true)}
        >
          Create database
        </button>
      </div>

      {error ? (
        <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              <th className="px-4 py-2 font-medium">Database</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {(data?.databases ?? []).map((database) => {
              const active = database === data?.active;
              return (
                <tr
                  key={database}
                  onClick={() => void select(database)}
                  className="cursor-pointer border-b border-slate-100 last:border-0 hover:bg-brand-cyan/5"
                >
                  <td className="whitespace-pre px-4 py-2 font-mono">{database}</td>
                  <td className="px-4 py-2">
                    {active ? (
                      <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                        active
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      type="button"
                      className="rounded border border-red-200 px-3 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-40"
                      disabled={busy}
                      onClick={(event) => {
                        event.stopPropagation();
                        setDeleting(database);
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              );
            })}
            {data && data.databases.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-slate-400">
                  No databases yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
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
          active={deleting === data?.active}
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-navy/60 p-4">
      <form
        className="w-full max-w-md space-y-4 rounded-lg bg-white p-6 shadow-xl"
        onSubmit={submit}
      >
        <div>
          <h3 className="text-lg font-semibold text-red-700">Delete database</h3>
          <p className="mt-2 text-sm text-slate-600">
            This permanently deletes <span className="whitespace-pre font-mono font-medium">{database}</span>,
            including every module, table and record in it. This cannot be undone.
          </p>
        </div>

        {active ? (
          <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            This is the active database. You will be returned to the database
            manager after it is deleted.
          </div>
        ) : null}

        {error ? (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">
            Type <span className="whitespace-pre font-mono">{database}</span> to confirm
          </span>
          <input
            autoFocus
            className="w-full rounded border border-slate-300 px-3 py-2 font-mono text-sm focus:border-red-500 focus:outline-none"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">
            Master key
          </span>
          <input
            type="password"
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-red-500 focus:outline-none"
            value={masterKey}
            onChange={(event) => setMasterKey(event.target.value)}
          />
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:border-brand-cyan hover:bg-brand-cyan/5"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="rounded bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-40"
            disabled={busy || confirm !== database || !masterKey}
          >
            {busy ? 'Deleting…' : 'Delete database'}
          </button>
        </div>
      </form>
    </div>
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-navy/60 p-4">
      <form
        className="w-full max-w-md space-y-4 rounded-lg bg-white p-6 shadow-xl"
        onSubmit={submit}
      >
        <h3 className="text-lg font-semibold">Create database</h3>

        {error ? (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">
            Database name
          </span>
          <input
            autoFocus
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30"
            placeholder="name"
            value={form.name}
            onChange={set('name')}
          />
          <span className="mt-1 block text-xs text-slate-400">
            Case and spaces are preserved. Up to 63 bytes.
          </span>
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">
            Admin username
          </span>
          <input
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30"
            value={form.adminLogin}
            onChange={set('adminLogin')}
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">
            Admin password
          </span>
          <input
            type="password"
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30"
            value={form.adminPassword}
            onChange={set('adminPassword')}
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">
            Master key
          </span>
          <input
            type="password"
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30"
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
            className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:border-brand-cyan hover:bg-brand-cyan/5"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="rounded bg-brand-blue px-4 py-2 text-sm font-medium text-white hover:bg-brand-blue-dark disabled:opacity-40"
            disabled={busy}
          >
            {busy ? 'Creating…' : 'Create'}
          </button>
        </div>
      </form>
    </div>
  );
}
