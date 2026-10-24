# Domain: Sales

## Purpose

The `sale` module demonstrates a header/lines business document with computed
totals, server-side on-change behavior and state actions. It depends on `core`
and `stock`.

## Models

### `sale.order` — table `sale_order`

- `name` — order reference (required; Python callers may leave it empty).
- `client_id` — many2one `sys.contact` (required).
- `date_order` — date, defaults to today.
- `state` — selection `draft`, `confirmed`, `done`, `cancelled`; default `draft`,
  read-only in forms.
- `amount_total` — computed sum of line subtotals (`@depends_on(['lines.subtotal'])`).
- `note` — free text.
- `@api_expose` instance actions: `confirm`, `done`, `cancel`, `reset_to_draft`;
  each calls `is_one()` and writes `state`.

### `sale.order.line` — table `sale_order_line`

- `order_id` — many2one `sale.order` (required; inverse of `order.lines`).
- `product_id` — many2one `stock.product` (required).
- `name`, `quantity` (default 1), `standard_price` (cost, read-only),
  `price_unit`, and computed `subtotal`.
- `@on_change(['product_id'])` copies the product name, cost and selling price.
- `@depends_on(['quantity', 'price_unit'])` computes `subtotal`.

## Behavior

- `order.lines` is discovered from `sale.order.line.order_id`; assigning
  `[(0, 0, {...})]` creates line drafts. The example in
  `modules/sale/models/sale_order_line.py` runs unchanged with an in-memory
  `SaleOrder.new()`, on-change-populated line fields, computed subtotal/total and
  `order.save()`.
- Forms use server drafts: the order and its lines share one token; line rows are
  added with `reuse: false`, edits go through the 800 ms draft queue, and parent
  `amount_total` is refreshed from server-computed draft values.
- `commit` writes the parent and lines atomically. Parent totals are recomputed
  after children exist.
- Uninstalling `sale` removes the Sales menu and its translation rows after a
  page refresh; its tables are dropped by the module manager.

## UI

- `modules/sale/ui/src/views/Orders.tsx` — orders list/cards, a form with a
  `FormTable` for lines, and Confirm/Done/Cancel row actions.
- `modules/sale/ui/src/views/OrderLines.tsx` — standalone line list/cards/form.
- `modules/sale/i18n/{en,ar,fr}.lang` — model/menu/view translations.
- Both pages use the shared `Page`/`Table`/`Cards`/`Form` kit and `t()` from
  `@jerp/locale`.

## Checks

- `sale` requires `core` + `stock`; install it in a test database.
- Run the model example against a temporary database to verify `amount_total`,
  `subtotal` and `state` without touching production data.
