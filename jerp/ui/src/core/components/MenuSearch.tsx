import * as React from 'react';

import { api } from '../api';
import type { MenuItem } from '../menu';
import { useAvailableModels } from '../models';

export type { MenuItem };

export interface MenuSearchProps {
  /** Menus visible to the current user (already auth-filtered). */
  menus: MenuItem[];
  /** Increment to focus the input again (Ctrl+K while the drawer is open). */
  focusKey?: number;
  onClose: () => void;
  onNavigate: (href: string) => void;
}

interface MenuTarget {
  kind: 'menu';
  key: string;
  label: string;
  path: string;
  href: string;
}

interface ModelTarget {
  kind: 'model';
  key: string;
  name: string;
}

interface RecordTarget {
  kind: 'record';
  key: string;
  model: string;
  id: number | string;
  label: string;
}

type Target = MenuTarget | ModelTarget | RecordTarget;

type Mode = 'all' | 'menu' | 'model' | 'record';

interface Parsed {
  mode: Mode;
  text: string;
  model?: string;
}

interface RecordResult {
  id: number | string;
  label: string;
}

function flattenMenus(items: MenuItem[], trail: string[] = []): MenuTarget[] {
  const result: MenuTarget[] = [];
  for (const item of items) {
    const path = [...trail, item.label];
    if (item.href) {
      result.push({
        kind: 'menu',
        key: `menu:${item.href}`,
        label: item.label,
        path: path.join(' / '),
        href: item.href,
      });
    }
    if (item.children && item.children.length > 0) {
      result.push(...flattenMenus(item.children, path));
    }
  }
  return result;
}

function matches(value: string, needle: string): boolean {
  return value.toLowerCase().includes(needle.toLowerCase());
}

function modelLabel(name: string): string {
  return name
    .split('.')
    .map((part) => part.replace(/_/g, ' '))
    .join(' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function parseQuery(raw: string, models: string[]): Parsed {
  if (raw.startsWith('/')) {
    return { mode: 'menu', text: raw.slice(1).trim() };
  }
  if (raw.startsWith('@')) {
    const rest = raw.slice(1);
    const space = rest.search(/\s/);
    if (space >= 0) {
      const token = rest.slice(0, space);
      const text = rest.slice(space + 1);
      const model = models.find(
        (name) => name.toLowerCase() === token.toLowerCase(),
      );
      if (model) {
        return { mode: 'record', model, text };
      }
    }
    return { mode: 'model', text: rest };
  }
  return { mode: 'all', text: raw.trim() };
}

function recordHref(view: string, id: number | string): string {
  const params = new URLSearchParams({
    name: view,
    view: 'form',
    id: String(id),
  });
  return `/view?${params.toString()}`;
}

function Section({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="py-1">
      <p className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/40">
        {title}
      </p>
      {children}
    </div>
  );
}

function ResultButton({
  active,
  icon,
  title,
  subtitle,
  hint,
  buttonRef,
  onClick,
}: {
  active: boolean;
  icon: string;
  title: string;
  subtitle?: string;
  hint?: string;
  buttonRef?: React.Ref<HTMLButtonElement>;
  onClick: () => void;
}) {
  return (
    <button
      ref={buttonRef}
      type="button"
      tabIndex={-1}
      onClick={onClick}
      className={`flex w-full items-center gap-2 rounded px-3 py-1.5 text-left text-sm transition ${
        active
          ? 'bg-white/15 text-white'
          : 'text-white/75 hover:bg-white/10 hover:text-white'
      }`}
    >
      <span className="flex h-5 w-5 flex-none items-center justify-center rounded bg-white/10 text-[11px] text-white/60">
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate">{title}</span>
        {subtitle ? (
          <span className="block truncate text-[11px] text-white/40">
            {subtitle}
          </span>
        ) : null}
      </span>
      {hint ? (
        <span className="flex-none text-[10px] uppercase tracking-wide text-white/30">
          {hint}
        </span>
      ) : null}
    </button>
  );
}

export function MenuSearch({
  menus,
  focusKey = 0,
  onClose,
  onNavigate,
}: MenuSearchProps) {
  const models = useAvailableModels();
  const [query, setQuery] = React.useState('');
  const [activeIndex, setActiveIndex] = React.useState(0);
  const [records, setRecords] = React.useState<RecordTarget[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const activeRef = React.useRef<HTMLButtonElement | null>(null);

  const modelNames = React.useMemo(() => Object.keys(models).sort(), [models]);
  const flatMenus = React.useMemo(() => flattenMenus(menus), [menus]);
  const parsed = parseQuery(query, modelNames);
  const recordModel = parsed.mode === 'record' ? parsed.model : undefined;
  const recordText = parsed.mode === 'record' ? parsed.text.trim() : '';

  React.useEffect(() => {
    inputRef.current?.focus();
  }, [focusKey]);

  // Fetch record matches with a short debounce; cancel stale responses.
  React.useEffect(() => {
    if (!recordModel || !recordText) {
      setRecords([]);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({
        model: recordModel,
        q: recordText,
        limit: '10',
      });
      api
        .getFresh<{ results: RecordResult[] }>(`/search?${params.toString()}`)
        .then((data) => {
          if (cancelled) {
            return;
          }
          setRecords(
            (data.results ?? []).map((result) => ({
              kind: 'record',
              key: `record:${recordModel}:${result.id}`,
              model: recordModel,
              id: result.id,
              label: result.label,
            })),
          );
        })
        .catch((err: unknown) => {
          if (cancelled) {
            return;
          }
          setRecords([]);
          setError(err instanceof Error ? err.message : String(err));
        })
        .finally(() => {
          if (!cancelled) {
            setLoading(false);
          }
        });
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [recordModel, recordText]);

  React.useEffect(() => {
    setActiveIndex(0);
  }, [query, records]);

  const menuTargets: MenuTarget[] = flatMenus.filter(
    (item) =>
      !parsed.text ||
      matches(item.label, parsed.text) ||
      matches(item.path, parsed.text),
  );
  const modelTargets: ModelTarget[] = modelNames
    .filter(
      (name) =>
        !parsed.text ||
        matches(name, parsed.text) ||
        matches(modelLabel(name), parsed.text),
    )
    .map((name) => ({ kind: 'model', key: `model:${name}`, name }));

  let targets: Target[];
  if (parsed.mode === 'menu') {
    targets = menuTargets;
  } else if (parsed.mode === 'model') {
    targets = modelTargets;
  } else if (parsed.mode === 'record') {
    targets = records;
  } else {
    targets = [...menuTargets, ...modelTargets];
  }

  const active = targets.length ? Math.min(activeIndex, targets.length - 1) : 0;
  const showPanel = query.trim().length > 0;

  React.useEffect(() => {
    activeRef.current?.scrollIntoView({ block: 'nearest' });
  }, [active]);

  const chooseModel = (name: string) => {
    setQuery(`@${name} `);
    setActiveIndex(0);
    inputRef.current?.focus();
  };

  const activate = (target: Target | undefined) => {
    if (!target) {
      return;
    }
    if (target.kind === 'menu') {
      onNavigate(target.href);
      return;
    }
    if (target.kind === 'model') {
      chooseModel(target.name);
      return;
    }
    const view = models[target.model];
    if (view) {
      onNavigate(recordHref(view, target.id));
    }
  };

  const move = (delta: number) => {
    if (!targets.length) {
      return;
    }
    setActiveIndex((current) => {
      const next = current + delta;
      return (next + targets.length) % targets.length;
    });
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      move(1);
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      move(-1);
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      activate(targets[active]);
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      if (query) {
        setQuery('');
        inputRef.current?.focus();
      } else {
        onClose();
      }
    }
  };

  const placeholder =
    parsed.mode === 'menu'
      ? 'Search menus…'
      : parsed.mode === 'model'
        ? 'Search models…'
        : parsed.mode === 'record'
          ? `Search ${parsed.model} records…`
          : 'Search menus or models…';

  const modelButtonRef = (index: number) =>
    active === index ? activeRef : undefined;

  return (
    <div className="space-y-2">
      <div className="relative">
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-white/40">
          ⌕
        </span>
        <input
          ref={inputRef}
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          aria-label="Search menus and records"
          autoFocus
          spellCheck={false}
          className="w-full rounded-lg border border-white/15 bg-white/10 py-2 pl-8 pr-16 text-sm text-white placeholder:text-white/35 focus:border-brand-cyan focus:outline-none focus:ring-2 focus:ring-brand-cyan/30"
        />
        <kbd className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-white/20 bg-white/10 px-1.5 py-0.5 text-[10px] text-white/50">
          Ctrl K
        </kbd>
      </div>

      <p className="px-1 text-[11px] text-white/35">
        <span className="text-white/55">/</span> menus ·{' '}
        <span className="text-white/55">@</span> records
      </p>

      {showPanel ? (
        <div className="max-h-[55vh] overflow-y-auto rounded-lg border border-white/10 bg-brand-navy-soft/90 shadow-lg">
          {parsed.mode === 'record' ? (
            <div className="border-b border-white/10 px-3 py-2">
              <div className="flex items-center gap-2">
                <span className="min-w-0 flex-1 truncate text-xs font-medium text-white/70">
                  {parsed.model}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setQuery('@');
                    inputRef.current?.focus();
                  }}
                  className="rounded px-1.5 py-0.5 text-[11px] text-white/50 hover:bg-white/10 hover:text-white"
                >
                  Change
                </button>
              </div>
              <p className="mt-0.5 text-[11px] text-white/35">
                {recordText
                  ? 'Matching records by name.'
                  : 'Type a name to search records.'}
              </p>
            </div>
          ) : null}

          {parsed.mode === 'model' ? (
            <Section title="Models">
              {modelTargets.length > 0 ? (
                modelTargets.map((target, index) => (
                  <ResultButton
                    key={target.key}
                    active={active === index}
                    icon="@"
                    title={target.name}
                    subtitle={modelLabel(target.name)}
                    hint="Select"
                    buttonRef={modelButtonRef(index)}
                    onClick={() => chooseModel(target.name)}
                  />
                ))
              ) : (
                <p className="px-3 py-2 text-xs text-white/40">
                  No models match.
                </p>
              )}
            </Section>
          ) : parsed.mode === 'record' ? (
            <Section title="Records">
              {loading ? (
                <p className="px-3 py-2 text-xs text-white/40">Searching…</p>
              ) : error ? (
                <p className="px-3 py-2 text-xs text-red-300">{error}</p>
              ) : !recordText ? (
                <p className="px-3 py-2 text-xs text-white/40">
                  Type a name to search {parsed.model} records.
                </p>
              ) : records.length > 0 ? (
                records.map((target, index) => (
                  <ResultButton
                    key={target.key}
                    active={active === index}
                    icon="›"
                    title={target.label}
                    subtitle={`@${target.model}`}
                    hint="Open"
                    buttonRef={modelButtonRef(index)}
                    onClick={() => activate(target)}
                  />
                ))
              ) : (
                <p className="px-3 py-2 text-xs text-white/40">
                  No records found.
                </p>
              )}
            </Section>
          ) : (
            <>
              <Section title="Menus">
                {menuTargets.length > 0 ? (
                  menuTargets.map((target, index) => (
                    <ResultButton
                      key={target.key}
                      active={active === index}
                      icon="↗"
                      title={target.label}
                      subtitle={target.path}
                      hint="Open"
                      buttonRef={modelButtonRef(index)}
                      onClick={() => activate(target)}
                    />
                  ))
                ) : (
                  <p className="px-3 py-2 text-xs text-white/40">
                    No menus match.
                  </p>
                )}
              </Section>

              {modelTargets.length > 0 ? (
                <Section title={`Models (${parsed.text ? 'matching' : '@'})`}>
                  {modelTargets.map((target, index) => {
                    const position = menuTargets.length + index;
                    return (
                      <ResultButton
                        key={target.key}
                        active={active === position}
                        icon="@"
                        title={target.name}
                        subtitle={modelLabel(target.name)}
                        hint="Search"
                        buttonRef={modelButtonRef(position)}
                        onClick={() => chooseModel(target.name)}
                      />
                    );
                  })}
                </Section>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
