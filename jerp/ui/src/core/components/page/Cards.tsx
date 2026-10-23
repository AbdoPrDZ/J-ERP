import * as React from 'react';

import { model } from '../../model';
import { formatValue, navigateTo } from '../../utils';
import { Pagination, PAGE_SIZES } from './Pagination';
import { RecordContext, usePage } from './context';
import { autoModelFields, useModelFields, useRelationLabels } from './useModelFields';

export interface CardFieldProps {
  name: string;
  label?: string;
  widget?: string;
  badge_colors?: Record<string, string>;
}

/** Declares a card field. Renders nothing on its own. */
export function CardField(_props: CardFieldProps) {
  return null;
}

export function isCardField(node: React.ReactNode): node is React.ReactElement<CardFieldProps> {
  return React.isValidElement(node) && node.type === CardField;
}

export interface CardsProps {
  model: string;
  title?: string;
  emptyMessage?: string;
  onCardClick?: (record: Record<string, unknown>) => void;
  children?: React.ReactNode;
}

const CARD_IMAGE_FIELD_NAMES = new Set(['image', 'logo', 'avatar']);

const BADGE_COLORS: Record<string, string> = {
  green: 'bg-emerald-100 text-emerald-700',
  red: 'bg-red-50 text-red-700',
  gray: 'bg-slate-100 text-slate-600',
  blue: 'bg-brand-blue/10 text-brand-blue',
  cyan: 'bg-brand-cyan/15 text-brand-cyan-dark',
  amber: 'bg-amber-50 text-amber-800',
};

function isCardImageField(field: {
  name: string;
  ttype?: string;
  relation?: string | null;
  hide?: boolean;
}): boolean {
  const isFileField =
    field.ttype === 'image' ||
    field.ttype === 'file' ||
    (field.ttype === 'many2one' && field.relation === 'sys.file');
  return (
    !field.hide &&
    isFileField &&
    CARD_IMAGE_FIELD_NAMES.has(field.name.toLowerCase())
  );
}

function CardImage({
  value,
  alt,
  fit,
}: {
  value: unknown;
  alt: string;
  fit: 'object-cover' | 'object-contain';
}) {
  const directSrc =
    typeof value === 'string' && value !== '' && !Number.isFinite(Number(value))
      ? value.startsWith('/') || value.startsWith('http')
        ? value
        : `/__storage/${value}`
      : null;
  const [path, setPath] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (
      directSrc ||
      value === null ||
      value === undefined ||
      value === '' ||
      Number(value) === 0 ||
      !Number.isFinite(Number(value))
    ) {
      setPath(null);
      return;
    }

    let cancelled = false;
    void (async () => {
      try {
        const file = await model('sys.file').find<{ path: string }>(
          value as number | string,
        );
        if (!cancelled) {
          setPath(file?.path ?? null);
        }
      } catch {
        if (!cancelled) {
          setPath(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [value, directSrc]);

  const src = directSrc ?? (path ? `/__storage/${path}` : null);
  if (!src) {
    return null;
  }

  return (
    <img
      src={src}
      alt={alt}
      className={`h-24 w-24 shrink-0 rounded-md border border-slate-200 bg-brand-white ${fit}`}
    />
  );
}

/** Cards over a model's records; fields come from ``CardField`` children. */
export function Cards({
  model: modelName,
  emptyMessage = 'No records.',
  onCardClick,
  children,
}: CardsProps) {
  const page = usePage();
  const active = !page || page.view === 'cards';

  const items = React.Children.toArray(children);
  const fields = items.filter(isCardField);
  const custom = items.filter((node) => !isCardField(node));
  const schema = useModelFields(modelName);
  const autoEnabled = page?.autoFields ?? true;
  const autoFields = React.useMemo(
    () =>
      autoEnabled
        ? autoModelFields(schema, new Set(fields.map((field) => field.props.name)))
        : [],
    [autoEnabled, schema, fields],
  );
  const fieldSpecs = [
    ...fields.map((field) => {
      const descriptor = schema.find((item) => item.name === field.props.name);
      return {
        name: field.props.name,
        label: field.props.label ?? descriptor?.label ?? field.props.name,
        help: descriptor?.help ?? null,
        relation: descriptor?.relation ?? null,
        selection: descriptor?.selection ?? null,
        widget: field.props.widget ?? null,
        badgeColors: field.props.badge_colors ?? null,
      };
    }),
    ...autoFields.map((field) => ({
      name: field.name,
      label: field.label ?? field.name,
      help: field.help ?? null,
      relation: field.relation ?? null,
      selection: field.selection ?? null,
      widget: null,
      badgeColors: null,
    })),
  ];
  const relationLabels = useRelationLabels(schema);
  const schemaImageField = schema.find(isCardImageField);
  const declaredImageField = fieldSpecs.find((field) =>
    CARD_IMAGE_FIELD_NAMES.has(field.name.toLowerCase()),
  );
  const imageFieldName = schemaImageField?.name ?? declaredImageField?.name;
  const imageFit =
    imageFieldName?.toLowerCase() === 'image'
      ? 'object-cover'
      : 'object-contain';
  const displayFields = fieldSpecs.filter(
    (field) => !CARD_IMAGE_FIELD_NAMES.has(field.name.toLowerCase()),
  );
  const titleField = displayFields[0];
  const detailFields = displayFields.slice(1);
  const fetchNames = Array.from(
    new Set([
      ...fieldSpecs.map((field) => field.name),
      ...(imageFieldName ? [imageFieldName] : []),
    ]),
  );

  const displayValue = (
    field: (typeof fieldSpecs)[number],
    record: Record<string, unknown>,
  ): string => {
    const raw = record[field.name];
    if (field.relation) {
      return relationLabels[field.relation]?.[String(raw)] ?? formatValue(raw);
    }
    if (field.selection) {
      const option = field.selection.find(
        ([key]) => String(key) === String(raw),
      );
      if (option) {
        return option[1];
      }
    }
    return formatValue(raw);
  };

  const renderValue = (
    field: (typeof fieldSpecs)[number],
    record: Record<string, unknown>,
  ): React.ReactNode => {
    const text = displayValue(field, record);
    if (field.widget !== 'badge') {
      return text;
    }
    const raw = record[field.name];
    const color = field.badgeColors?.[String(raw)] ?? 'gray';
    return (
      <span
        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
          BADGE_COLORS[color] ?? BADGE_COLORS.gray
        }`}
      >
        {text}
      </span>
    );
  };

  const [records, setRecords] = React.useState<Record<string, unknown>[]>([]);
  const [total, setTotal] = React.useState(0);
  const [error, setError] = React.useState<string | null>(null);
  const [pageNumber, setPageNumber] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(PAGE_SIZES[0]);
  const [loading, setLoading] = React.useState(false);
  const loadId = React.useRef(0);

  const fieldKey = fetchNames.join(',');
  const load = React.useCallback(async () => {
    if (!active) {
      return;
    }
    const requestId = ++loadId.current;
    setLoading(true);
    setError(null);
    try {
      const [data, count] = await Promise.all([
        model(modelName).all<Record<string, unknown>>({
          fields: fieldKey ? fieldKey.split(',') : undefined,
          limit: pageSize,
          offset: (pageNumber - 1) * pageSize,
        }),
        model(modelName).count(),
      ]);
      if (requestId !== loadId.current) {
        return;
      }
      setRecords(data);
      setTotal(count);
    } catch (err) {
      if (requestId === loadId.current) {
        setError((err as Error).message);
      }
    } finally {
      if (requestId === loadId.current) {
        setLoading(false);
      }
    }
  }, [active, modelName, fieldKey, pageSize, pageNumber]);

  React.useEffect(() => {
    void load();
  }, [load]);

  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  React.useEffect(() => {
    if (pageNumber > pageCount) {
      setPageNumber(pageCount);
    }
  }, [pageNumber, pageCount]);

  const changePageSize = (value: number) => {
    setPageSize(value);
    setPageNumber(1);
  };

  if (!active) {
    return null;
  }

  const cardClick =
    onCardClick ??
    (page?.open ? (record: Record<string, unknown>) => navigateTo({ view: 'form', id: record.id }) : undefined);

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      {error ? (
        <div className="flex-none rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}
      <div
        className={`grid min-h-0 flex-1 auto-rows-max grid-cols-1 content-start gap-4 overflow-y-auto transition-opacity sm:grid-cols-2 lg:grid-cols-3 ${
          loading ? 'opacity-60' : ''
        }`}
        aria-busy={loading}
      >
        {records.map((record, index) => (
          <RecordContext.Provider key={String(record.id ?? index)} value={record}>
            <div
              onClick={cardClick ? () => cardClick(record) : undefined}
              className={`flex items-start gap-4 rounded-lg border border-slate-200 bg-white p-4 ${
                cardClick ? 'cursor-pointer hover:border-brand-cyan hover:bg-brand-cyan/5' : ''
              }`}
            >
              {imageFieldName ? (
                <CardImage
                  value={record[imageFieldName]}
                  alt={String(
                    record._label ??
                      (titleField ? record[titleField.name] : '') ??
                      '',
                  )}
                  fit={imageFit}
                />
              ) : custom.length > 0 ? (
                <div className="shrink-0">{custom}</div>
              ) : null}
              <div className="min-w-0 flex-1">
                {imageFieldName && custom.length > 0 ? (
                  <div className="mb-2">{custom}</div>
                ) : null}
                {titleField ? (
                  <>
                    <h3
                      className="font-medium text-brand-navy"
                      title={titleField.help ?? undefined}
                    >
                      {renderValue(titleField, record)}
                    </h3>
                    {detailFields.length > 0 ? (
                      <dl className="mt-2 space-y-1 text-sm">
                        {detailFields.map((field, fieldIndex) => (
                          <div key={fieldIndex} className="flex gap-2">
                            <dt
                              className="shrink-0 text-slate-400"
                              title={field.help ?? undefined}
                            >
                              {field.label}
                            </dt>
                            <dd className="truncate text-slate-600">
                              {renderValue(field, record)}
                            </dd>
                          </div>
                        ))}
                      </dl>
                    ) : null}
                  </>
                ) : null}
              </div>
            </div>
          </RecordContext.Provider>
        ))}
        {records.length === 0 ? (
          <p className="text-sm text-slate-400">{emptyMessage}</p>
        ) : null}
      </div>

      <Pagination
        page={pageNumber}
        pageSize={pageSize}
        total={total}
        onPageChange={setPageNumber}
        onPageSizeChange={changePageSize}
        disabled={loading}
      />
    </div>
  );
}
