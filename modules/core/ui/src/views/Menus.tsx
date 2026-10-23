import * as React from 'react';
import { Page, PageContent } from '@jerp/ui';

interface MenuItem {
  label: string;
  href?: string;
  img?: string;
  auth?: boolean;
  sequence?: number;
  description?: string;
  add_to_home?: boolean;
  children?: MenuItem[];
}

/** Menus are injected by the server from the installed modules' configure.json. */
function readMenus(): MenuItem[] {
  const element = document.getElementById('__JERP_MENUS__');
  if (!element?.textContent) {
    return [];
  }
  try {
    const value = JSON.parse(element.textContent);
    return Array.isArray(value) ? (value as MenuItem[]) : [];
  } catch {
    return [];
  }
}

function targetLabel(item: MenuItem): string {
  if (!item.href) {
    return 'Group';
  }
  try {
    const url = new URL(item.href, window.location.origin);
    return url.searchParams.get('name') ?? item.href;
  } catch {
    return item.href;
  }
}

function MenuRows({
  items,
  depth = 0,
}: {
  items: MenuItem[];
  depth?: number;
}) {
  return (
    <>
      {items.map((item, index) => (
        <React.Fragment key={`${depth}-${index}-${item.label}`}>
          <tr className="border-b border-slate-100 last:border-0 hover:bg-brand-cyan/5">
            <td className="px-3 py-2 text-slate-700">
              <span style={{ paddingLeft: `${depth * 20}px` }}>
                {depth > 0 ? (
                  <span className="mr-1 text-slate-300">└</span>
                ) : null}
                {item.label}
                {item.add_to_home ? (
                  <span className="ml-2 rounded-full bg-brand-cyan/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-brand-cyan-dark">
                    Home
                  </span>
                ) : null}
              </span>
            </td>
            <td className="px-3 py-2">
              {item.href ? (
                <a
                  href={item.href}
                  className="text-brand-blue hover:underline"
                >
                  {targetLabel(item)}
                </a>
              ) : (
                <span className="text-slate-400">Group</span>
              )}
            </td>
            <td className="px-3 py-2 text-right text-slate-500">
              {item.sequence ?? 0}
            </td>
            <td className="px-3 py-2 text-right text-slate-400">
              {item.auth === false ? 'public' : 'private'}
            </td>
          </tr>
          {item.children && item.children.length > 0 ? (
            <MenuRows items={item.children} depth={depth + 1} />
          ) : null}
        </React.Fragment>
      ))}
    </>
  );
}

export default function Menus() {
  const menus = React.useMemo(readMenus, []);

  return (
    <Page
      name="core.menus"
      title="Menus"
      searchBar={false}
      create={false}
      update={false}
      delete={false}
      open={false}
      views={['list']}
      autoFields={false}
    >
      <PageContent>
        <div className="space-y-3">
          <p className="text-sm text-slate-500">
            Menu entries come from each installed module&apos;s
            <code className="mx-1 rounded bg-slate-100 px-1">configure.json</code>
            routes. Groups have no target; pages link to their view or endpoint.
          </p>
          <div className="overflow-hidden rounded-lg border border-slate-200">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-brand-white text-left text-slate-500">
                  <th className="px-3 py-2 font-medium">Label</th>
                  <th className="px-3 py-2 font-medium">View / endpoint</th>
                  <th className="px-3 py-2 text-right font-medium">Sequence</th>
                  <th className="px-3 py-2 text-right font-medium">Access</th>
                </tr>
              </thead>
              <tbody>
                {menus.length > 0 ? (
                  <MenuRows items={menus} />
                ) : (
                  <tr>
                    <td
                      colSpan={4}
                      className="px-3 py-5 text-center text-slate-400"
                    >
                      No menus are configured.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </PageContent>
    </Page>
  );
}
