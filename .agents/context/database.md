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
- `sys_model` / `sys_field` persist the model/field-to-column mapping. This is
  what makes **renames deterministic**: a declared field whose column is missing
  can be matched to a previously stored column and renamed instead of dropped
  and recreated.
- Indexes created and dropped by the syncer are named `<table>_<column>_idx`.
  Only indexes with that managed prefix/suffix are ever dropped.
- Virtual models (`_virtual = True`) have no table; the syncer skips them.
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

## Data Safety

- Schema sync **drops columns** for fields no longer declared, and uninstalling
  a module **drops its tables**. Treat both as destructive.
- Renames are inferred; if inference is wrong the old column can be dropped.
- DDL runs transactionally, so a failed sync leaves the database unchanged.
- Never run destructive database operations (drop database/table, uninstall a
  module) without explicit user confirmation.

## Typical Tables

`sys_module`, `sys_model`, `sys_field`, `users`, `files` (core) and `products`
(stock). This is not an inventory — modules add their own tables when installed.
