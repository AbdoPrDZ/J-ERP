# Database

## Model

- **PostgreSQL only.** `jerp.dialect.PostgresDialect` generates all DDL and
  normalizes `information_schema` results; identifiers are always quoted.
- Connections are configured in `jerp.config.json` (`databases.host/port/user/
  password/sslmode/owner`) and overridden by `JERP_DB_*` environment variables.
- The target schema defaults to `public` (`schema` in config).
- One PostgreSQL **database per tenant/workspace** is the core design. Each has
  its own installed modules and therefore its own table/field set.
- Pools are created lazily on first use (`psycopg_pool`, min 1 / max 10).
- No database is created or assumed at application startup.

## Declarative Schema (no migration files)

- Tables come from model classes: subclass `jerp.models.Model`, declare
  `jerp.fields.*` attributes, set `_table` (and optionally `_name`).
- `jerp.schema.SchemaSyncer` compares declared fields with the live schema and,
  in a single transaction, creates tables, adds columns, alters types,
  adjusts nullability, drops removed columns, and manages indexes.
- When a required field is added to a non-empty table it is backfilled with a
  neutral value (`0` for numbers, `''` for text, `FALSE`, `CURRENT_DATE`) before
  `NOT NULL` is applied; required relations that cannot be guessed still fail.
- Type changes drop an incompatible column default first, cast the column, then
  restore the declared default. This matters for `text` → `jsonb` migrations.
- `sys_model` / `sys_field` persist the model/field-to-column mapping. This is
  what makes **renames deterministic**: a declared field whose column is missing
  can be matched to a previously stored column and renamed instead of dropped
  and recreated.
- Indexes created and dropped by the syncer are named `<table>_<column>_idx`.
  Only indexes with that managed prefix/suffix are ever dropped.
- Virtual models (`_virtual = True`) have no table; the syncer skips them.
- Computed fields keep their column; stored values are recomputed by the model
  runtime. Optional computed fields are nullable.
- `core` is always installed first and owns the system tables.

## Standard Columns And Naming

- Every model inherits `id`, `created_at`, `updated_at`.
- Model class `Product` → `_name`/`_table` `product` / `product` by default;
  dotted logical names are allowed (`sys.module` → table `sys_module`).
- Field attribute name is the column name unless `column_name` is set; the
  field `name` is only the human label.
- `unique`/`index` become managed indexes; `required` controls `NOT NULL`.
- `hide=True` keeps a field writable through the API but removes its value from
  record reads (used for passwords).
- The API accepts an underscore alias for dotted model names
  (`sys_module` → `sys.module`).

## Server-Side Drafts

- `temp.model` stores unsaved form/table rows for the new draft API. It is a
  transient core table (`_temporary = True`, no external refs) with:
  `token`, `model`, `record_id`, `state` (`create`/`update`/`delete`), `data`
  (TEXT JSON snapshot), `dirty` (JSONB changed values), `version`, `base_stamp`.
- Drafts are grouped by a per-form token. `new`/`edit` create or reuse them;
  `change` runs on-change + compute and stores new values; `commit` writes all
  rows of a token in one transaction (parent + children) and deletes the drafts.
- `base_stamp` detects concurrent changes to the real record before commit.
- The table is not part of the business schema; it can be cleared safely, but
  active forms lose their unsaved state.

## Data Safety

- Schema sync **drops columns** for fields no longer declared, and uninstalling
  a module **drops its tables**. Treat both as destructive.
- Renames are inferred; if inference is wrong the old column can be dropped.
- DDL runs transactionally, so a failed sync leaves the database unchanged.
- Never run destructive database operations (drop database/table, uninstall a
  module) without explicit user confirmation.

## Typical Tables

`sys_module`, `sys_model`, `sys_field`, `sys_lang`, `sys_contact`, `sys_user`,
`sys_file`, `temp_model` (core), `stock_product` (stock), `sale_order` and
`sale_order_line` (sale). This is not an inventory — modules add their own
tables when installed.
