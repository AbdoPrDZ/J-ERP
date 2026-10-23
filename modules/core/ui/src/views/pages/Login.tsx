import * as React from 'react';
import { api } from '@jerp/ui';

export default function Login() {
  const [username, setUsername] = React.useState('admin');
  const [password, setPassword] = React.useState('');
  const [showPassword, setShowPassword] = React.useState(false);
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
    <div className="relative flex min-h-[calc(100dvh-1.5rem)] items-center justify-center overflow-hidden rounded-2xl bg-brand-white px-1 py-6 sm:px-4">
      {/* Soft brand wash behind the whole page. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(60rem 36rem at 8% 8%, rgba(34, 211, 238, 0.16), transparent 55%), radial-gradient(48rem 32rem at 92% 92%, rgba(37, 99, 235, 0.14), transparent 55%)',
        }}
      />

      <div className="relative grid w-full max-w-6xl items-center gap-10 px-2 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16 lg:px-6">
        {/* Brand story — desktop only, so the form stays the focus on mobile. */}
        <section className="hidden lg:block">
          <img
            src="/__assets/core/logo-full.png"
            alt="J-ERP — Modular ERP Framework"
            className="h-auto w-full max-w-[26rem]"
          />

          <p className="mt-10 text-xs font-semibold uppercase tracking-[0.24em] text-brand-cyan-dark">
            Modular ERP platform
          </p>
          <h1 className="mt-3 max-w-lg text-4xl font-semibold leading-tight tracking-tight text-brand-navy xl:text-5xl">
            One workspace for your whole business.
          </h1>
          <p className="mt-4 max-w-md text-base leading-relaxed text-slate-500">
            Sales, inventory, contacts and configuration — connected by design,
            ready to grow with you.
          </p>

          <div className="mt-8 flex flex-wrap gap-2">
            {['Modular', 'Secure', 'Fast'].map((label) => (
              <span
                key={label}
                className="rounded-full border border-brand-blue/15 bg-white/70 px-3 py-1 text-xs font-medium text-brand-navy shadow-sm backdrop-blur"
              >
                {label}
              </span>
            ))}
          </div>
        </section>

        <section className="mx-auto w-full max-w-md">
          {/* Full logo on small screens, where the brand panel is hidden. */}
          <div className="mb-6 flex justify-center lg:hidden">
            <img
              src="/__assets/core/logo-full.png"
              alt="J-ERP — Modular ERP Framework"
              className="h-auto w-full max-w-[17rem]"
            />
          </div>

          <form
            className="relative overflow-hidden rounded-2xl border border-brand-navy/10 bg-white/95 p-7 shadow-xl shadow-brand-navy/10 backdrop-blur sm:p-9"
            onSubmit={submit}
          >
            <div
              aria-hidden="true"
              className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-brand-cyan via-brand-blue to-brand-navy"
            />

            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-brand-cyan-dark">
              Welcome back
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-brand-navy">
              Sign in to J-ERP
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Use your workspace credentials to continue.
            </p>

            {error ? (
              <div
                role="alert"
                className="mt-5 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
              >
                {error}
              </div>
            ) : null}

            <div className="mt-6 space-y-4">
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-slate-700">
                  Username
                </span>
                <input
                  className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-brand-navy shadow-sm transition focus:border-brand-blue focus:outline-none focus:ring-4 focus:ring-brand-cyan/20"
                  value={username}
                  autoComplete="username"
                  autoFocus
                  onChange={(event) => setUsername(event.target.value)}
                />
              </label>

              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-slate-700">
                  Password
                </span>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 pr-16 text-sm text-brand-navy shadow-sm transition focus:border-brand-blue focus:outline-none focus:ring-4 focus:ring-brand-cyan/20"
                    value={password}
                    autoComplete="current-password"
                    onChange={(event) => setPassword(event.target.value)}
                  />
                  <button
                    type="button"
                    className="absolute inset-y-0 right-0 px-3 text-xs font-medium text-brand-blue hover:text-brand-blue-dark focus:outline-none focus-visible:underline"
                    onClick={() => setShowPassword((value) => !value)}
                  >
                    {showPassword ? 'Hide' : 'Show'}
                  </button>
                </div>
              </label>
            </div>

            <button
              type="submit"
              className="mt-6 w-full rounded-lg bg-brand-blue px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-blue-dark disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-cyan/30"
              disabled={busy}
            >
              {busy ? 'Signing in…' : 'Sign in'}
            </button>

            <p className="mt-5 text-center text-xs leading-relaxed text-slate-400">
              Need access? Contact your workspace administrator.
            </p>
          </form>
        </section>
      </div>
    </div>
  );
}
