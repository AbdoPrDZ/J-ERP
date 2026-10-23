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
  /** Render model fields not explicitly declared in the view. */
  autoFields: boolean;
  setView: (view: string) => void;
}

export const PageContext = createContext<PageConfig | null>(null);

export function usePage(): PageConfig | null {
  return useContext(PageContext);
}

/** The record currently selected in a table/cards, provided to custom content. */
export const RecordContext = createContext<Record<string, unknown> | null>(null);

export interface DraftQueueHandle {
  flush: () => Promise<void>;
  dispose: () => void;
  lastErrors?: Record<string, string>;
}

/** Draft/session context shared by a form and its embedded tables/widgets. */
export interface DraftContextValue {
  token: string;
  model?: string;
  draftId?: number | null;
  recordId?: number | string | null;
  values: Record<string, unknown>;
  registerQueue: (queue: DraftQueueHandle) => () => void;
  flushAll: () => Promise<void>;
  discardAll: () => Promise<void>;
  draftsVersion: number;
  notifyDraftsChanged: () => void;
}

export const DraftContext = createContext<DraftContextValue | null>(null);

/** True when a table/cards view is rendered inside a form tab. */
export const FormTabContext = createContext(false);
