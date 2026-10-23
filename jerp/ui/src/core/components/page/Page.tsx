import * as React from 'react';

import { model } from '../../model';
import { navigateTo } from '../../utils';
import { PageContext, type PageConfig } from './context';

const VIEW_LABELS: Record<string, string> = {
  list: 'List',
  cards: 'Cards',
  form: 'Form',
};

export interface BreadcrumbItem {
  label: string;
  onClick?: () => void;
}

/** Breadcrumb. Clicking an item goes back to it. */
export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav className="flex flex-wrap items-center gap-1 text-lg">
      {items.map((item, index) => (
        <React.Fragment key={index}>
          {index > 0 ? <span className="text-slate-300">/</span> : null}
          {item.onClick ? (
            <button
              type="button"
              onClick={item.onClick}
              className="rounded px-1 font-semibold text-slate-500 hover:bg-slate-100 hover:text-slate-900"
            >
              {item.label}
            </button>
          ) : (
            <span className="px-1 font-semibold text-slate-900">{item.label}</span>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
}

export interface PageProps {
  name: string;
  title?: string;
  img?: string;
  /** Model used to resolve the record's label for the path. */
  model?: string;
  /** Field used as the record's label (default ``name``). */
  labelField?: string;
  /** Show the search box (default true). */
  searchBar?: boolean;
  /** Show the Create button (default true). */
  create?: boolean;
  /** Allow editing — the form is editable when true (default true). */
  update?: boolean;
  /** Show the Delete action (default true). */
  delete?: boolean;
  /** Clicking a row/card opens the record (default true). */
  open?: boolean;
  /** View types offered by the switcher (default ['list', 'cards']). */
  views?: string[];
  children?: React.ReactNode;
}

export function Page({
  name,
  title,
  img,
  model: modelName,
  labelField = 'name',
  searchBar = true,
  create = true,
  update = true,
  delete: canDelete = true,
  open = true,
  views = ['list', 'cards'],
  children,
}: PageProps) {
  const params = new URLSearchParams(window.location.search);
  const view = params.get('view') || views[0] || 'list';
  const id = params.get('id') ?? undefined;
  const editing = view === 'form';

  const [recordLabel, setRecordLabel] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!modelName || view !== 'form' || !id) {
      setRecordLabel(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const record = await model(modelName).find<Record<string, unknown>>(id);
        if (!cancelled) {
          const label = record?._label ?? record?.[labelField];
          setRecordLabel(label ? String(label) : `#${id}`);
        }
      } catch {
        if (!cancelled) {
          setRecordLabel(`#${id}`);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [modelName, view, id, labelField]);

  const setView = (next: string) => {
    navigateTo({ view: next === views[0] ? undefined : next, id: undefined });
  };

  const breadcrumb: BreadcrumbItem[] = [
    {
      label: title ?? name,
      onClick: editing ? () => setView(views[0] ?? 'list') : undefined,
    },
  ];
  if (editing) {
    breadcrumb.push({ label: recordLabel ?? (id ? `#${id}` : 'New') });
  }

  const config: PageConfig = {
    name,
    title,
    img,
    view,
    id,
    views,
    searchBar,
    create,
    update,
    delete: canDelete,
    open,
    setView,
  };

  return (
    <PageContext.Provider value={config}>
      <div className="space-y-6">
        <PageHeader
          title={title}
          breadcrumb={breadcrumb}
          searchBar={searchBar && !editing}
          views={editing ? [] : views}
          view={view}
          onView={setView}
          create={create && !editing}
          onCreate={() => navigateTo({ view: 'form', id: undefined })}
        />
        {children}
      </div>
    </PageContext.Provider>
  );
}

export interface PageHeaderProps {
  title?: string;
  breadcrumb?: BreadcrumbItem[];
  searchBar?: boolean;
  views?: string[];
  view?: string;
  onView?: (view: string) => void;
  create?: boolean;
  onCreate?: () => void;
  children?: React.ReactNode;
}

/** The page header (path/title + search + view switcher + create). Rendered by Page. */
export function PageHeader({
  title,
  breadcrumb,
  searchBar,
  views,
  view,
  onView,
  create,
  onCreate,
  children,
}: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      {breadcrumb && breadcrumb.length > 0 ? (
        <Breadcrumb items={breadcrumb} />
      ) : (
        <h2 className="text-xl font-semibold">{title}</h2>
      )}
      <div className="flex flex-wrap items-center gap-2">
        {searchBar ? (
          <input
            type="search"
            placeholder="Search…"
            className="rounded border border-slate-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          />
        ) : null}

        {views && views.length > 1 ? (
          <div className="flex overflow-hidden rounded border border-slate-300">
            {views.map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => onView?.(type)}
                className={`px-3 py-1.5 text-sm ${
                  type === view
                    ? 'bg-slate-100 text-slate-900'
                    : 'text-slate-500 hover:bg-slate-50'
                }`}
              >
                {VIEW_LABELS[type] ?? type}
              </button>
            ))}
          </div>
        ) : null}

        {create ? (
          <button
            type="button"
            onClick={onCreate}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Create
          </button>
        ) : null}

        {children}
      </div>
    </div>
  );
}

export function PageContent({ children }: { children?: React.ReactNode }) {
  return <div className="space-y-4">{children}</div>;
}
