import * as React from 'react';
import { api } from '@jerp/ui';

export default function Home({ context }: { context: Record<string, unknown> }) {
  const user = (context.user as string | undefined) ?? '';
  const [busy, setBusy] = React.useState(false);

  const logout = async () => {
    if (busy) {
      return;
    }
    setBusy(true);
    try {
      await api.post('/logout');
    } catch {
      // ignore - we navigate away regardless
    }
    window.location.assign('/');
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <img src="/__assets/core/logo.png" alt="J-ERP" className="h-9 w-9 rounded" />
        <div className="flex-1">
          <h2 className="text-xl font-semibold text-brand-navy">Hello, {user}</h2>
          <p className="text-sm text-slate-500">Welcome back to J-ERP.</p>
        </div>
        <button
          type="button"
          className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:border-brand-cyan hover:bg-brand-cyan/5 disabled:opacity-40"
          disabled={busy}
          onClick={() => void logout()}
        >
          Log out
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <a
          href="/view?name=core.modules"
          className="flex flex-col justify-between rounded-lg border border-slate-200 bg-white p-5 hover:border-brand-cyan hover:bg-brand-cyan/5"
        >
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
            Modules
          </p>
          <p className="mt-2 text-lg text-brand-blue">Manage →</p>
        </a>
      </div>
    </div>
  );
}
