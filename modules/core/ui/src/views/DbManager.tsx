import * as React from 'react';
import { api } from '@jerp/ui';

interface DatabasesResponse {
  databases: string[];
  active: string | null;
  error: string | null;
}

const emptyForm = { name: '', adminLogin: 'admin', adminPassword: '' };

export default function DbManager() {
  const [data, setData] = React.useState<DatabasesResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [creating, setCreating] = React.useState(false);

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
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
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
            </tr>
          </thead>
          <tbody>
            {(data?.databases ?? []).map((database) => {
              const active = database === data?.active;
              return (
                <tr
                  key={database}
                  onClick={() => void select(database)}
                  className="cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50"
                >
                  <td className="px-4 py-2 font-mono">{database}</td>
                  <td className="px-4 py-2">
                    {active ? (
                      <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                        active
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {data && data.databases.length === 0 ? (
              <tr>
                <td colSpan={2} className="px-4 py-6 text-center text-slate-400">
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
    const name = form.name.trim().toLowerCase();
    if (!name || !form.adminPassword || busy) {
      setError(!name ? 'A database name is required.' : 'An admin password is required.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post('/databases', {
        name,
        admin_login: form.adminLogin.trim() || 'admin',
        admin_password: form.adminPassword,
      });
      await api.post('/databases/select', { name });
      onCreated();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
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
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            placeholder="name"
            value={form.name}
            onChange={set('name')}
          />
          <span className="mt-1 block text-xs text-slate-400">
            Lowercase letters, digits and underscores.
          </span>
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">
            Admin username
          </span>
          <input
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
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
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            value={form.adminPassword}
            onChange={set('adminPassword')}
          />
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
            disabled={busy}
          >
            {busy ? 'Creating…' : 'Create'}
          </button>
        </div>
      </form>
    </div>
  );
}
