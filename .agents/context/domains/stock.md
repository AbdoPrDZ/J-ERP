# Domain: Stock

## Purpose

The `stock` module is the first business module and the template for new
modules. It demonstrates the minimal end-to-end slice: manifest → model →
screen → menu.

## Structure

- `modules/stock/configure.json` — name `stock`, version, summary,
  `depends: ["core"]`, and one `Stock` menu group with a **Products** entry
  (`view: stock.products`, params `{ "view": "list" }`).
- `modules/stock/models/product.py` — model `stock.product`, table
  `stock_product`, fields `name` (required), `image` (`ImageField`),
  `standard_price` (cost) and `price` (selling price), both floats.
- `modules/stock/ui/src/views/Products.tsx` — `Page` with Table/Cards/Form for
  the product model; uses `TableField`/`FormField` for the product fields.
- The Stock menu group has `sequence: 30`; Products is flagged `add_to_home` so
  it appears on the Home dashboard while the module is installed.

## Behavior

- Products are ordinary model records: the standard model API
  (`/api/model/stock.product/...`) provides list/count/find/create/update/delete.
- Product images use the core upload flow: a `sys.file` record is stored and the
  image field holds its id; files are served at `/__storage/<token>`.
- `standard_price` is the internal cost; `price` is the default selling price used
  by sale order lines.
- The menu and Home shortcut appear only where the `stock` module is installed.
- Stock cannot be installed without `core`; uninstalling stock drops
  `stock_product`.

## Extending

- Add fields in the model; update the module so the schema syncs.
- When a stock feature becomes a meaningful domain of its own (orders,
  inventory movements, pricing), promote it to its own module rather than
  growing a single catch-all module — and only then add a domain context file
  if the business rules justify it.
- Keep stock-specific behavior out of `jerp/` and out of `core`.
