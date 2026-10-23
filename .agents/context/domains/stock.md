# Domain: Stock

## Purpose

The `stock` module is the first business module and the template for new
modules. It demonstrates the minimal end-to-end slice: manifest → model →
screen → menu.

## Structure

- `modules/stock/configure.json` — name `stock`, version, summary,
  `depends: ["core"]`, and one `Stock` menu group with a **Products** entry
  (`view: stock.products`, params `{ "view": "list" }`).
- `modules/stock/models/product.py` — model `product`, table `products`, fields
  `name` (required) and `image` (`ImageField`).
- `modules/stock/ui/src/views/Products.tsx` — `Page` with Table/Cards/Form for
  the `product` model; uses `TableField`/`FormField` for `name` and `image`.
- Built output: `data/view/stock/Products.js` (+ manifest).

## Behavior

- Products are ordinary model records: the standard model API
  (`/api/model/product/...`) provides list/count/find/create/update/delete.
- Product images use the core upload flow: a `file` record is stored and the
  image field holds its id; files are served at `/__storage/<token>`.
- The menu appears only where the `stock` module is installed for that database.
- Stock cannot be installed without `core`; uninstalling stock drops
  `products`.

## Extending

- Add fields in the model; update the module so the schema syncs.
- When a stock feature becomes a meaningful domain of its own (orders,
  inventory movements, pricing), promote it to its own module rather than
  growing a single catch-all module — and only then add a domain context file
  if the business rules justify it.
- Keep stock-specific behavior out of `jerp/` and out of `core`.
