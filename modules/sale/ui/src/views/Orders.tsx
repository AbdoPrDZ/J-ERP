import * as React from 'react';
import {
  Page,
  PageContent,
  Table,
  TableField,
  FormTable,
  Cards,
  CardField,
  Form,
  FormField,
  FormGroup,
  FormTabs,
  FormTab,
  RecordContext,
  model,
} from '@jerp/ui';

interface Product {
  id: number;
  name?: string;
  _label?: string;
}

interface Line {
  id: number;
  product_id: number;
  name: string;
  quantity: number;
  price_unit: number;
  subtotal: number;
}

/** Inline line editor shown inside the sale order form. */
function OrderLines() {
  const record = React.useContext(RecordContext);
  const rawId = record?.id;
  const orderId =
    rawId === null || rawId === undefined ? null : Number(rawId);

  const [lines, setLines] = React.useState<Line[]>([]);
  const [products, setProducts] = React.useState<Product[]>([]);
  const [productId, setProductId] = React.useState('');
  const [description, setDescription] = React.useState('');
  const [quantity, setQuantity] = React.useState('1');
  const [price, setPrice] = React.useState('0');
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    if (!orderId) {
      setLines([]);
      return;
    }
    try {
      const rows = await model('sale.order.line').all<Line>({
        domain: [['order_id', '=', orderId]],
        order: 'id',
      });
      setLines(rows);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [orderId]);

  React.useEffect(() => {
    void load();
  }, [load]);

  React.useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const rows = await model('stock.product').all<Product>({ limit: 200 });
        if (!cancelled) {
          setProducts(rows);
        }
      } catch {
        if (!cancelled) {
          setProducts([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!orderId) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-5 text-sm text-slate-500">
        Save the order first to add lines.
      </div>
    );
  }

  const add = async () => {
    if (!productId || busy) {
      return;
    }
    const product = products.find((item) => String(item.id) === productId);
    const label =
      description.trim() || product?._label || product?.name || 'Line';

    setBusy(true);
    setError(null);
    try {
      await model('sale.order.line').create({
        order_id: orderId,
        product_id: Number(productId),
        name: label,
        quantity: Number(quantity) || 0,
        price_unit: Number(price) || 0,
      });
      window.location.reload();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    if (busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await model('sale.order.line').delete(id);
      window.location.reload();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold">Order lines</h3>
        <span className="text-sm text-slate-400">{lines.length} line(s)</span>
      </div>

      {error ? (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-lg border border-slate-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-brand-white text-left text-slate-500">
              <th className="px-3 py-2 font-medium">Product</th>
              <th className="px-3 py-2 font-medium">Description</th>
              <th className="px-3 py-2 font-medium">Qty</th>
              <th className="px-3 py-2 font-medium">Unit price</th>
              <th className="px-3 py-2 font-medium">Subtotal</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {lines.map((line) => (
              <tr key={line.id} className="border-b border-slate-100 last:border-0 hover:bg-brand-cyan/5">
                <td className="px-3 py-2 text-slate-700">
                  {products.find(
                    (item) => String(item.id) === String(line.product_id),
                  )?._label ?? `#${line.product_id}`}
                </td>
                <td className="px-3 py-2 text-slate-700">{line.name}</td>
                <td className="px-3 py-2 text-slate-700">{line.quantity}</td>
                <td className="px-3 py-2 text-slate-700">
                  {Number(line.price_unit ?? 0).toFixed(2)}
                </td>
                <td className="px-3 py-2 font-medium text-brand-navy">
                  {Number(line.subtotal ?? 0).toFixed(2)}
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    type="button"
                    className="rounded border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-40"
                    disabled={busy}
                    onClick={() => void remove(line.id)}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
            {lines.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-3 py-5 text-center text-slate-400"
                >
                  No lines yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 gap-2 md:grid-cols-6">
        <select
          className="rounded border border-slate-300 px-3 py-2 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30 md:col-span-2"
          value={productId}
          onChange={(event) => setProductId(event.target.value)}
        >
          <option value="">Select product…</option>
          {products.map((product) => (
            <option key={product.id} value={product.id}>
              {product._label ?? product.name ?? `#${product.id}`}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Description"
          className="rounded border border-slate-300 px-3 py-2 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30 md:col-span-2"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
        <input
          type="number"
          step="any"
          placeholder="Qty"
          className="rounded border border-slate-300 px-3 py-2 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30"
          value={quantity}
          onChange={(event) => setQuantity(event.target.value)}
        />
        <input
          type="number"
          step="any"
          placeholder="Unit price"
          className="rounded border border-slate-300 px-3 py-2 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30"
          value={price}
          onChange={(event) => setPrice(event.target.value)}
        />
        <button
          type="button"
          className="rounded bg-brand-blue px-4 py-2 text-sm font-medium text-white hover:bg-brand-blue-dark disabled:opacity-40 md:col-span-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60"
          disabled={busy || !productId}
          onClick={() => void add()}
        >
          {busy ? 'Saving…' : 'Add line'}
        </button>
      </div>
    </div>
  );
}

export default function Orders() {
  return (
    <Page
      name="sale.orders"
      title="Sale Orders"
      model="sale.order"
      searchBar
      create
      update
      delete
      views={['list', 'cards']}
    >
      <PageContent>
        <Table
          model="sale.order"
          emptyMessage="No sale orders found."
          actions={[
            { label: 'Confirm', method: 'confirm', key: 'id', style: 'primary' },
            { label: 'Done', method: 'done', key: 'id' },
            { label: 'Cancel', method: 'cancel', key: 'id', style: 'danger' },
          ]}
        >
          <TableField name="name" />
          <TableField name="client_id" />
          <TableField name="date_order" />
          <TableField name="state" />
          <TableField name="amount_total" />
        </Table>

        <Cards model="sale.order" emptyMessage="No sale orders found.">
          <CardField name="name" />
          <CardField name="client_id" />
          <CardField name="date_order" />
          <CardField name="state" />
          <CardField name="amount_total" />
        </Cards>

        <Form model="sale.order" title="Sale Order">
          <FormGroup label="Order">
            <FormField name="name" />
            <FormField name="client_id" />
            <FormField name="date_order" />
            <FormField name="state" />
            <FormField name="amount_total" />
          </FormGroup>

          <FormTabs>
            <FormTab label="Lines">
              <FormTable model="sale.order.line" emptyMessage="No lines found.">
                <TableField name="product_id" />
                <TableField name="name" />
                <TableField name="quantity" />
                <TableField name="price_unit" />
                <TableField name="subtotal" />
              </FormTable>
            </FormTab>
            <FormTab label="Notes">
              <FormField name="note" />
            </FormTab>
          </FormTabs>
        </Form>
      </PageContent>
    </Page>
  );
}
