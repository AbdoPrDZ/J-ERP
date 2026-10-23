import { createContext, useContext } from 'react';

export interface PageMeta {
  name: string;
  title?: string;
  img?: string;
}

export interface PageConfig {
  name: string;
  title?: string;
  img?: string;
  /** Active view type: list | cards | form | ... */
  view: string;
  /** Record id (from the URL) when editing. */
  id?: string;
  /** View types available in the switcher. */
  views: string[];
  searchBar: boolean;
  create: boolean;
  /** Allow editing (the form is editable). */
  update: boolean;
  /** Show the per-row Delete action. */
  delete: boolean;
  /** Clicking a row/card opens the record in the form view. */
  open: boolean;
  setView: (view: string) => void;
}

export const PageContext = createContext<PageConfig | null>(null);

export function usePage(): PageConfig | null {
  return useContext(PageContext);
}

/** The record currently selected in a table/cards, provided to custom content. */
export const RecordContext = createContext<Record<string, unknown> | null>(null);
