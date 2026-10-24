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
  in a single transaction, creates tables, adds columns, adjusts nullability,
  applies lossless type changes (explicit syncs only), manages indexes, renames
  columns declared with `renamed_from`, and drops columns only when
  `allow_drop=True`.
- When a required field is added to a non-empty table it is backfilled with a
  neutral value (`0` for numbers, `''` for text, `FALSE`, `CURRENT_DATE`) before
  `NOT NULL` is applied; required relations that cannot be guessed still fail.
  A **nullable** added column is not backfilled.
- A type change is applied only when `PostgresDialect.can_cast_losslessly()`
  accepts the pair (integer widening, `numeric` widening, varchar widening,
  anything → `text`, `date` → `timestamp`, `json` ↔ `jsonb`). Anything that can
  truncate or re-parse values is reported as `blocked`. An accepted change drops
  an incompatible column default first, casts, then restores the declared
  default (relevant when a column becomes `jsonb`).
- `sys_model` / `sys_field` persist the model/field-to-column mapping. Renames
  are **never guessed**: only a field that declares `renamed_from='old_attr'`
  gets `ALTER TABLE ... RENAME COLUMN`, after the old name is resolved through
  `sys_field` (`renamed_from` is consumed once).
- `sys_field.state` is `active` or `retired`. A field that is no longer declared
  keeps its row and column as `retired`; dropping it needs `allow_drop=True`.
- A sync always produces a `SchemaPlan` (`changes`, `blocked`, `warnings`,
  `destructive`, `as_dict()`), and each change carries its SQL. `plan()` /
  `sync_models(..., mode='plan')` builds one without executing DDL;
  `Registry.last_schema_plan` keeps the last one.
- `Registry.preview(name, allow_drop)` plans a whole-database sync without
  touching it (`name` only validates that the module is installed);
  `Registry.retired_fields()` lists retired columns still present.
- The request path (`Registry.sync_dirty()` through `ensure_loaded`) applies
  safe changes, including declared renames, but reports lossless type changes as
  blocked ("safe but deferred") and never drops. Blocked work is logged and kept
  in `last_schema_plan`; it does not fail the request.
- Explicit `init_models()` / install / update apply lossless type changes and
  raise `SchemaBlocked` after the safe part has committed. A blocked rename also
  skips adding its target column, so the rename can still run later.
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

- Schema sync **never guesses a rename** and **never drops a column by default**:
  a removed field is marked `retired` and its data stays in place.
  `allow_drop=True` drops recorded, undeclared columns; uninstalling a module
  **drops its tables**. Treat the latter two as destructive.
- Lossy type changes are blocked, not applied; resolve them deliberately.
- DDL for one sync runs in one transaction, so an error rolls that sync back.
  `SchemaBlocked` is raised *after* the transaction commits the safe part, so a
  blocked plan can leave additive changes applied.
- Preview before changing: `module.preview` (Modules dialog),
  `update --dry-run`, and `doctor` (retired columns plus `DROP COLUMN` SQL) are
  read-only. `--allow-drop` is database-wide.
- Never run destructive database operations (drop database/table, uninstall a
  module, `allow_drop`) without explicit user confirmation.

## Typical Tables

`sys_module`, `sys_model`, `sys_field`, `sys_lang`, `sys_contact`, `sys_user`,
`sys_file`, `temp_model` (core), `stock_product` (stock), `sale_order` and
`sale_order_line` (sale). This is not an inventory — modules add their own
tables when installed.
