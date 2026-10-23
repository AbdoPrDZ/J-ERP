import * as React from 'react';
import { api } from '@jerp/ui';

export default function Login() {
  const [username, setUsername] = React.useState('admin');
  const [password, setPassword] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post<{ user: string }>('/login', { username, password });
      window.location.assign('/home');
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-[70vh] items-center justify-center">
      <form
        className="w-full max-w-sm space-y-5 rounded-lg border border-brand-navy/10 border-t-4 border-t-brand-cyan bg-white p-8 shadow-sm"
        onSubmit={submit}
      >
        <div className="flex items-center gap-3">
          <img src="/__assets/core/logo.png" alt="J-ERP" className="h-10 w-10 rounded" />
          <h2 className="text-xl font-semibold text-brand-navy">Sign in</h2>
        </div>

        {error ? (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">Username</span>
          <input
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">Password</span>
          <input
            type="password"
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>

        <button
          type="submit"
          className="w-full rounded bg-brand-blue px-4 py-2 text-sm font-medium text-white hover:bg-brand-blue-dark disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60"
          disabled={busy}
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}
