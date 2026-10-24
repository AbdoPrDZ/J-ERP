import * as React from 'react';
import { model } from '@jerp/ui';

interface StatDef {
  key: string;
  module: string;
  model: string;
  label: string;
  description: string;
  tone: string;
}

const STAT_DEFS: StatDef[] = [
  {
    key: 'contacts',
    module: 'core',
    model: 'sys.contact',
    label: 'Contacts',
    description: 'People and organisations',
    tone: 'bg-brand-cyan',
  },
  {
    key: 'orders',
    module: 'sale',
    model: 'sale.order',
    label: 'Sales orders',
    description: 'Quotes and confirmations',
    tone: 'bg-brand-blue',
  },
  {
    key: 'products',
    module: 'stock',
    model: 'stock.product',
    label: 'Products',
    description: 'Items in the catalogue',
    tone: 'bg-emerald-400',
  },
  {
    key: 'users',
    module: 'core',
    model: 'sys.user',
    label: 'Users',
    description: 'Workspace accounts',
    tone: 'bg-slate-400',
  },
];

export default function Home({ context }: { context: Record<string, unknown> }) {
  const user = (context.user as string | undefined) ?? '';
  const [installed, setInstalled] = React.useState<string[] | null>(null);
  const [counts, setCounts] = React.useState<Record<string, number | null>>({});

  React.useEffect(() => {
    let cancelled = false;

    void (async () => {
      let installedModules = new Set(['core']);
      try {
        const modules = await model('module').all<{
          name: string;
          state: string;
        }>();
        installedModules = new Set(
          modules
            .filter((row) => row.state === 'installed')
            .map((row) => row.name),
        );
      } catch {
        // Keep the core-only fallback; the page still works without it.
      }
      if (cancelled) {
        return;
      }
      setInstalled([...installedModules]);

      const defs = STAT_DEFS.filter((stat) =>
        installedModules.has(stat.module),
      );
      const results = await Promise.allSettled(
        defs.map((stat) => model(stat.model).count()),
      );
      if (cancelled) {
        return;
      }
      const next: Record<string, number | null> = {};
      results.forEach((result, index) => {
        next[defs[index].key] =
          result.status === 'fulfilled' ? result.value : null;
      });
      setCounts(next);
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const installedSet = new Set(installed ?? ['core']);
  const visibleStats = STAT_DEFS.filter((stat) =>
    installedSet.has(stat.module),
  );

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand-navy via-brand-navy-soft to-brand-blue px-6 py-8 text-white shadow-lg sm:px-8">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              'radial-gradient(28rem 18rem at 100% 0%, rgba(34, 211, 238, 0.24), transparent 60%), radial-gradient(24rem 16rem at 0% 100%, rgba(37, 99, 235, 0.35), transparent 60%)',
          }}
        />

        <div className="relative flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-brand-cyan">
              Workspace overview
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              Welcome back{user ? `, ${user}` : ''}.
            </h1>
            <p className="mt-3 max-w-xl text-sm leading-relaxed text-white/70">
              Everything important in one place — contacts, sales, stock and your
              workspace configuration.
            </p>
          </div>

        </div>
      </section>

      {visibleStats.length > 0 ? (
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {visibleStats.map((stat) => {
            const value = counts[stat.key];
            return (
              <div
                key={stat.key}
                className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                    {stat.label}
                  </p>
                  <span className={`h-2.5 w-2.5 rounded-full ${stat.tone}`} />
                </div>
                <p className="mt-3 text-2xl font-semibold tracking-tight text-brand-navy">
                  {value === undefined || value === null ? '—' : value}
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  {value === null ? 'Not available' : stat.description}
                </p>
              </div>
            );
          })}
        </section>
      ) : null}
    </div>
  );
}
