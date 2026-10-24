import * as React from 'react';

import { t } from '../../i18n';
import { model } from '../../model';
import { navigateTo } from '../../utils';
import { PageContext, type PageConfig } from './context';

const VIEW_LABELS: Record<string, string> = {
  list: 'app.view.list',
  cards: 'app.view.cards',
  form: 'app.view.form',
};

export interface BreadcrumbItem {
  label: string;
  onClick?: () => void;
}

/** Breadcrumb. Clicking an item goes back to it. */
export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav className="flex flex-wrap items-center gap-1 text-base">
      {items.map((item, index) => (
        <React.Fragment key={index}>
          {index > 0 ? <span className="text-slate-300">/</span> : null}
          {item.onClick ? (
            <button
              type="button"
              onClick={item.onClick}
              className="rounded px-1 font-semibold text-slate-500 hover:bg-slate-100 hover:text-brand-navy"
            >
              {item.label}
            </button>
          ) : (
            <span className="px-1 font-semibold text-brand-navy">{item.label}</span>
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
  /** Show the record name (or "New") after the page title in the path (default true). */
  recordBreadcrumb?: boolean;
  /** Allow editing — the form is editable when true (default true). */
  update?: boolean;
  /** Show the Delete action (default true). */
  delete?: boolean;
  /** Clicking a row/card opens the record (default true). */
  open?: boolean;
  /** View types offered by the switcher (default ['list', 'cards']). */
  views?: string[];
  /** Append model fields not explicitly declared (default true). */
  autoFields?: boolean;
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
  recordBreadcrumb = true,
  update = true,
  delete: canDelete = true,
  open = true,
  views = ['list', 'cards'],
  autoFields = true,
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
      onClick:
        editing && recordBreadcrumb ? () => setView(views[0] ?? 'list') : undefined,
    },
  ];
  if (editing && recordBreadcrumb) {
    breadcrumb.push({ label: recordLabel ?? (id ? `#${id}` : t('app.new')) });
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
    autoFields,
    setView,
  };

  return (
    <PageContext.Provider value={config}>
      <div className="flex h-full min-h-0 flex-col gap-3">
        <div className="flex-none -mx-4 border-b border-slate-200/80 bg-brand-white px-4 py-2">
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
        </div>
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
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {breadcrumb && breadcrumb.length > 0 ? (
          <Breadcrumb items={breadcrumb} />
        ) : (
          <h2 className="text-base font-semibold">{title}</h2>
        )}
        <div className="flex flex-wrap items-center gap-2">
          {create ? (
            <button
              type="button"
              onClick={onCreate}
              className="rounded bg-brand-blue px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-blue-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60"
            >
              {t('app.create')}
            </button>
          ) : null}

          {children}
        </div>
      </div>

      {searchBar || (views && views.length > 1) ? (
        <div className="flex flex-wrap items-center gap-2">
          {searchBar ? (
            <input
              type="search"
              placeholder={t('app.search')}
              className="min-w-0 flex-1 rounded border border-slate-300 px-3 py-1.5 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30"
            />
          ) : null}

          {views && views.length > 1 ? (
            <div className="flex overflow-hidden rounded border border-slate-300">
              {views.map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => onView?.(type)}
                  className={`px-3 py-1 text-sm ${
                    type === view
                      ? 'bg-brand-blue text-white'
                      : 'text-slate-500 hover:bg-brand-white hover:text-brand-navy'
                  }`}
                >
                  {VIEW_LABELS[type] ? t(VIEW_LABELS[type]) : type}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function PageContent({ children }: { children?: React.ReactNode }) {
  return (
    <div className="min-h-0 flex-1 space-y-4 overflow-y-auto">{children}</div>
  );
}
