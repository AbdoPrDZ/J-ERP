import * as React from 'react';

export const PAGE_SIZES = [10, 25, 50, 100];

const PAGE_BUTTON =
  'rounded border border-slate-300 px-2 py-1 text-sm text-slate-700 hover:border-brand-cyan hover:bg-brand-cyan/5 disabled:cursor-not-allowed disabled:opacity-40';

export interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  disabled?: boolean;
}

/** Server-side pagination controls shared by the table and cards views. */
export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  disabled = false,
}: PaginationProps) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const firstRow = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const lastRow = Math.min(page * pageSize, total);

  return (
    <div className="flex flex-none flex-wrap items-center justify-between gap-3 text-sm text-slate-600">
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2">
          <span>Rows per page</span>
          <select
            aria-label="Rows per page"
            value={pageSize}
            disabled={disabled}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
            className="rounded border border-slate-300 bg-white px-2 py-1 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30 disabled:opacity-60"
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
        <span className="text-slate-400">•</span>
        <span>
          {total === 0 ? 'No records' : `${firstRow}–${lastRow} of ${total}`}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-1">
        <button
          type="button"
          aria-label="First page"
          className={PAGE_BUTTON}
          disabled={disabled || page <= 1}
          onClick={() => onPageChange(1)}
        >
          «
        </button>
        <button
          type="button"
          aria-label="Previous page"
          className={PAGE_BUTTON}
          disabled={disabled || page <= 1}
          onClick={() => onPageChange(Math.max(1, page - 1))}
        >
          Prev
        </button>
        <span className="px-2">
          Page {page} of {pageCount}
        </span>
        <button
          type="button"
          aria-label="Next page"
          className={PAGE_BUTTON}
          disabled={disabled || page >= pageCount}
          onClick={() => onPageChange(Math.min(pageCount, page + 1))}
        >
          Next
        </button>
        <button
          type="button"
          aria-label="Last page"
          className={PAGE_BUTTON}
          disabled={disabled || page >= pageCount}
          onClick={() => onPageChange(pageCount)}
        >
          »
        </button>
      </div>
    </div>
  );
}
