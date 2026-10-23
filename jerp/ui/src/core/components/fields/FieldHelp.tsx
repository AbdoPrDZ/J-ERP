import * as React from 'react';

/**
 * Small ``?`` badge that reveals field help on hover or keyboard focus.
 *
 * The tooltip is positioned above the badge and rendered in a high stacking
 * layer, so it stays readable inside forms and grid layouts.
 */
export function FieldHelp({ text }: { text: string }) {
  return (
    <span
      tabIndex={0}
      aria-label={text}
      className="group/help relative inline-flex cursor-help items-center justify-center rounded-full border border-slate-300 px-1.5 text-[10px] font-semibold leading-4 text-slate-400 hover:border-brand-cyan hover:text-brand-blue focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60"
    >
      ?
      <span
        role="tooltip"
        className="pointer-events-none invisible absolute bottom-full left-0 z-40 mb-2 w-64 rounded-md bg-brand-navy px-3 py-2 text-left text-xs font-normal leading-snug text-white opacity-0 shadow-lg transition-opacity group-hover/help:visible group-hover/help:opacity-100 group-focus-within/help:visible group-focus-within/help:opacity-100"
      >
        {text}
      </span>
    </span>
  );
}
