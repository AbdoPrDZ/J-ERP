import * as React from 'react';

export interface ActionContextValue {
  close: () => void;
}

export const ActionContext = React.createContext<ActionContextValue | null>(null);

export function useAction(): ActionContextValue | null {
  return React.useContext(ActionContext);
}

export interface ActionProps {
  label: string;
  children?: React.ReactNode;
  open?: boolean;
  onClose?: () => void;
}

/** A modal action. Declared as a child of Form; listed in its ⋯ menu. */
export function Action({ children, open, onClose }: ActionProps) {
  if (!open) {
    return null;
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-navy/60 p-4">
      <div className="w-full max-w-md overflow-hidden rounded-lg bg-white shadow-xl">
        <ActionContext.Provider value={{ close: onClose ?? (() => {}) }}>
          {children}
        </ActionContext.Provider>
      </div>
    </div>
  );
}

export function isAction(node: React.ReactNode): node is React.ReactElement<ActionProps> {
  return React.isValidElement(node) && node.type === Action;
}

export function ActionHeader({ children }: { children?: React.ReactNode }) {
  const action = useAction();
  return (
    <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
      <h3 className="text-base font-semibold">{children}</h3>
      <button
        type="button"
        onClick={() => action?.close()}
        className="rounded px-2 text-slate-400 hover:bg-brand-cyan/10 hover:text-brand-blue"
      >
        ✕
      </button>
    </div>
  );
}

export function ActionContent({ children }: { children?: React.ReactNode }) {
  return <div className="space-y-4 px-5 py-4">{children}</div>;
}

export function ActionFooter({ children }: { children?: React.ReactNode }) {
  return (
    <div className="flex justify-end gap-2 border-t border-slate-200 px-5 py-3">
      {children}
    </div>
  );
}
