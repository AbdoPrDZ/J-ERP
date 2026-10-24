# Plan: schema sync safety and versioned migrations

- **Status:** Steps 1-2 implemented (2026-10-24); Steps 3-4 proposed
- **Date:** 2026-10-24
- **Based on:** `.agents/reviews/ChatGPT-Review.md` items 5-7 and
  `.agents/reviews/Claude-Review.md` section "Schema sync", verified against
  `22440d9` by reading `jerp/schema.py`, `jerp/modules.py`, `jerp/registry.py`,
  `jerp/db.py`, `jerp/cli.py`.
- **Touches:** `jerp/schema.py`, `jerp/fields.py`, `jerp/registry.py`,
  `jerp/modules.py`, `jerp/cli.py`, `modules/core/models/module.py`,
  `modules/core/configure.json` (version bump only), `tests/`.

## 1. Problem

Schema sync is the only part of J-ERP that can destroy data silently, and it
runs from three different entry points without a preview.

**A. Renames are guessed.** `_apply_renames` (`jerp/schema.py:162`) iterates the
declared fields, and for any field whose column is missing it takes the *first*
stored field that is no longer declared, as long as its old column still
exists, and renames that column. There is no mapping and no type check, so:

```python
# before
discount = fields.FloatField(name='Discount', default=0.0)
# after - one release, both edits
margin = fields.FloatField(name='Margin', default=0.0)
```

`discount`'s column is renamed to `margin`, and every historical discount is now
read as a margin. If the new field has a different type, `_apply_type_changes`
(`schema.py:248`) follows with `ALTER COLUMN ... TYPE ... USING col::type`
(`jerp/dialect.py:114`), so the mislabelled data is also coerced.

**B. Drops are automatic.** `_apply_drops` (`schema.py:278`) runs after adds and
type changes and issues `DROP COLUMN` for every stored field that is no longer
declared. Removing a field from a model deletes its data on the next sync.

**C. Version is ignored.** `configure.json` has `version`, `sys.module.version`
stores it, `install()` skips unchanged versions (`modules.py:126`) - but the
syncer never reads it. There is no ordered hook for a data transformation, and
no way to express "copy this column into that one before the rename".

**D. The destructive sync is triggered by ordinary requests.** `Registry.load()`
sets `_schema_synced = False` when a model fingerprint changed
(`registry.py:42-70`), and `ensure_loaded()` calls `sync_dirty()`
(`registry.py:73-85, 144-162`). Every controller calls `ensure_loaded()` (for
example `model_api.py:37`). So after deploying code, the **first API request**
applies pending adds, renames, and drops, with no UI, no CLI, and no
confirmation. Gating the "Update" button alone would not fix this.

## 2. Target behaviour

Safe changes stay automatic; anything that can lose or reinterpret data requires
an explicit decision.

| Operation | Today | Proposed |
|---|---|---|
| Create table | automatic | automatic |
| Add nullable column | automatic | automatic |
| Add column with a static default | automatic | automatic |
| Add required column, non-empty table, no default | raises | raises (unchanged) |
| Create/drop managed index | automatic | automatic |
| Rename field, `renamed_from` declared | guessed | `ALTER TABLE ... RENAME COLUMN`, automatic |
| Rename field, not declared | guessed, wrong data possible | **refused**, reported as "added + undeclared column" |
| Remove field | `DROP COLUMN` | column kept, field marked retired, reported |
| Remove field, `allow_drop` | `DROP COLUMN` | `DROP COLUMN` |
| Type change | `USING col::type`, always | automatic only for lossless pairs, otherwise refused (list in §3.5) |
| Data transform | impossible | `migrations/<version>/pre-*.py` / `post-*.py`, same transaction |
| Preview | none | plan object + exact SQL, CLI and UI |
| Version record | before sync, autocommit | last step of the same transaction |

## 3. Design

### 3.1 `renamed_from` on fields

`jerp/fields.py` already accepts `column_name` (`fields.py:72, 85, 110`) and the
syncer already tracks field→column in `sys_field`. Add one keyword:

```python
class Field:
  def __init__(self, ..., column_name=None, renamed_from=None, ...):
    self.renamed_from = renamed_from
```

`_apply_renames` becomes: for each declared field missing its column, if
`field.renamed_from` is set and `stored[renamed_from]` exists and that column is
present, rename `stored[renamed_from]` to `field.column_name`. Everything else
is left alone and reported. `renamed_from` is consumed once: after the sync,
`sys_field` holds only the new name, so a second run is a no-op.

The existing legacy model rename (`model._rename_from`, `schema.py:361`) is the
precedent for this shape; a table rename and a column rename should look alike.

### 3.2 Plan / apply split

`sync_models(models)` gains a mode and returns a `SchemaPlan`:

```python
@dataclass
class SchemaPlan:
  models: list[str]
  created: list[str]                 # tables
  added: list[ColumnChange]
  renamed: list[ColumnChange]        # old, new, via='renamed_from'
  retired: list[ColumnChange]        # left in place
  dropped: list[ColumnChange]
  altered: list[ColumnChange]        # type / nullability
  indexes: list[str]
  warnings: list[str]
  blocked: list[str]                 # would have been destructive, not applied
```

Implementation: each `_apply_*` method already builds its SQL through
`self.dialect` before executing. Give the syncer a `plan` argument; when
`plan.mode == 'plan'`, append the descriptor (and the SQL string the dialect
already returns) and skip `cur.execute` for DDL. Reads (`information_schema`,
`sys_field`) still run. This keeps the preview and the real run on the same code
path, so they cannot drift; no recorder cursor, no second diff engine.

`sync_models(models, *, mode='apply', allow_drop=False)`; `plan()` is a thin
wrapper. Any `blocked` entry turns a planned apply into a refused apply unless
the caller passed `allow_drop=True` or fixed the declaration.

SQL is attached to each change because it is already a string: `add_column_sql`,
`rename_column_sql`, `drop_column_sql`, `alter_type_sql`, `set_not_null_sql`,
`create_index_sql` (`jerp/dialect.py:107-160`). The only statements that stay
descriptor-only are the backfill `UPDATE`s in `_apply_adds`.

### 3.3 Trigger policy

Three entry points, three rules:

| Trigger | Rule |
|---|---|
| `ensure_loaded()` / `sync_dirty()` on a request | apply **additive** changes and **declared** renames; never drop or type-change. Blocked items surface in the plan and in the log. |
| `module.install` / `module.update` (UI and CLI) | plan first, show it, apply on confirm. Drops need `allow_drop`. |
| `python -m jerp.cli update --dry-run` / `--allow-drop` | explicit operator action, full apply allowed with the flag. |

Concretely, `sync_dirty()` passes `mode='apply', allow_drop=False` and
swallows `blocked` into a log line plus a cached plan. A request never fails
because of a pending rename; it fails only if an additive change is impossible
(the existing "required field without default" error).

### 3.4 Retired-field metadata

`_write_metadata` deletes `sys_field` rows for fields that are no longer declared
(`schema.py:356`). If drops become opt-in, the orphan column survives but its
row disappears, and `_apply_drops` iterates `stored`, not the live catalog - the
column becomes invisible and unmappable forever.

Add a `state` field to `SysField` (`modules/core/models/module.py`):
`active` / `retired`, default `active`. `_write_metadata` then:

- updates declared fields to `state='active'`;
- marks undeclared rows `state='retired'` instead of deleting;
- never deletes a `sys_field` row unless its column was actually dropped.

`_stored_fields` keeps returning both, and `_apply_drops` only considers
`retired` rows, so an `active` field's column cannot be dropped by mistake.
The `sys_field.state` column itself is added by the normal sync (nullable plus
default), so the migration is additive and safe.

Add `jerp doctor` (or `cli doctor`): list retired fields whose column exists,
grouped by model, with the SQL that would drop them. This is the "cleanup is
deliberate" tool that replaces the automatic drop.

### 3.5 Type changes

`alter_type_sql` always casts (`USING col::type`). Classify the pairs:

- **Allowed automatically:** varchar↔text, int→bigint→numeric, numeric
  precision/scale widening, anything→text.
- **Refused without a migration script:** text→number/date/bool, numeric→int,
  numeric narrowing, any other pair where `USING` can raise on existing rows.

The classification belongs in `jerp/dialect.py` (`can_cast_losslessly(old,
new)`), not in the syncer, so the preview and the executor share it. A refused
change appears in `blocked` with the pair and the offending field; the fix is a
`pre-` script that cleans the data, then a normal sync.

### 3.6 Transaction boundary

`sync_models` already wraps its whole model set in one transaction
(`schema.py:26-34`), and nested `db.transaction()` calls reuse the active
connection via `_active_transaction` (`jerp/db.py:70-98`). What is missing is
that the version row is written before the sync:

```python
# jerp/modules.py:117-131, 133-154 (current)
self._record(info)          # autocommit INSERT/UPDATE of the new version
self.build_views(module_name)
# ... later, in Registry.update: load() + init_models() -> sync_models()
```

The moment migrations are keyed on version this becomes a correctness bug: a
failed sync leaves the version advanced, and the retry skips the migration.

New order for `install` / `update`, in `Registry` (which owns the transaction):

1. resolve order, validate, `build_views` (outside the transaction - it spawns
   `node`, `modules.py:276-295`);
2. open one `db.transaction()`;
3. run `pre-*.py` for every module in order (old schema);
4. `sync_models(all target models)` - one transaction, shared connection;
5. run `post-*.py` for every module in order (new schema);
6. `_record(info)` for each module - version and state written **last**;
7. commit; then seeds and refs (`_apply_seeds`, `_ensure_refs`) outside.

Step 3 must not use model classes, only `cr` and raw SQL: the ORM still
describes the old schema at that point, which is exactly the Odoo `pre` contract.

`uninstall` gets the same treatment: one transaction over every `drop_model`
call, the extension-column reduction, and the `DELETE FROM sys_module`, with
`load()`/`init_models()` inside it. Today each `drop_model` is its own
transaction (`modules.py:178-185`), so a mid-way failure leaves tables dropped
and the module still recorded.

### 3.7 Migration runner

```
modules/<name>/
  configure.json          # "version": "1.1.0"
  migrations/
    1.1.0/
      pre-backfill_margin.py
      post-rename_currency.py
```

- Discover version folders under `migrations/`, sort by numeric tuple
  (`1.10.0` > `1.9.0`), run every folder with
  `installed_version < folder <= target_version`.
- Each script defines `migrate(cr, version)`; `version` is the previously
  installed version (`None`/`0.0.0` on install).
- `pre-*` runs before the sync, `post-*` after, same transaction, in folder
  order then filename order.
- No `end-*` phase initially. Odoo's `end` means "after every module upgraded";
  J-ERP's per-module update has no natural database-wide hook. If cross-module
  data fixes are needed, put them in a module that depends on all involved
  modules, or add `end` later as a database-level pass over all target modules.
- Failure handling: the transaction rolls back, including the version row and
  `build_views` output is already on disk (harmless - it is derived from code,
  not data).
- Runner lives in `jerp/migrations.py`, called by `Registry.install/update`, not
  by `ModuleManager`, because it needs the sync order and the transaction.

`configure.json` version becomes meaningful: bump it in the same commit as the
migration folder. `update(force=True)` still re-syncs, but migrations only run
when the version moved - `force` must not re-run data scripts.

### 3.8 Preview surface

- CLI: `python -m jerp.cli update --database <db> [module] --dry-run` prints
  the plan (model, operation, column, SQL) and exits non-zero if
  `plan.blocked`. `--allow-drop` applies drops.
- API: `module.preview` (`@api_expose` on `Module` in
  `modules/core/models/module.py`) returns the plan as JSON. `module.update`
  keeps its signature and gains `allow_drop=False`.
- UI: the Modules page "Update" action calls `preview`, renders the blocked /
  retired lists in a confirmation dialog, then calls `update`. `allow_drop`
  starts false in the dialog and needs a second, explicit toggle.
- `__storage`-like `/api` calls are unaffected.

## 4. Work order

Each step is independently shippable.

### Step 1 - no-guess renames, no auto-drop (approx. 1 day) — **done**

- [x] `jerp/fields.py`: add `renamed_from`, document it in the class docstring.
- [x] `jerp/schema.py`: rewrite `_apply_renames` to use `renamed_from` only;
      unmatched declared fields and undeclared columns become `add_column` /
      `retire_column` plan entries (a missing `renamed_from` target is
      `blocked`, not a warning, because it is an explicit contradiction).
- [x] `jerp/schema.py`: `_apply_drops` takes `allow_drop`; when false, append to
      `retired` and leave the column.
- [x] `jerp/schema.py`: `sync_models(..., mode='apply', allow_drop=False)` and a
      `SchemaPlan` dataclass; thread `plan` through the `_apply_*` methods.
- [x] `jerp/schema.py`: `_write_metadata` marks retired fields instead of
      deleting (blocked on Step 2's column, or ship together).
- [x] `modules/sale/models/sale_order_line.py`, `sale_order.py`,
      `stock/models/product.py`, `core/models/*`: no `renamed_from` needed yet;
      verify a clean sync produces zero warnings.

Verification: create a scratch database, rename `discount`→`margin` on a test
model with data, run sync, confirm the column is **not** renamed and the plan
reports both the add and the orphan.

**Step 1 notes / deviations from the design above**

- `sync_models` returns a `SchemaPlan` with a flat `changes` list
  (`op`, `model`, `table`, `column`, `sql`, …) instead of the separate
  `created` / `added` / `renamed` lists sketched in §3.2. A flat list keeps
  ordering (renames before adds before type changes before drops) which the
  preview and the executor both need, and `op` is enough to group.
- `plan()` never raises: blocked entries are returned in `plan.blocked` so a
  preview can show them. `mode='apply'` raises `SchemaBlocked` after the
  transaction commits the safe part; `allow_unsafe=True` returns the plan
  instead (used by tooling and tests).
- `renamed_from` pointing at a field that is *still declared*, or at a name
  absent from `sys_field`, is a `blocked` entry rather than a silent no-op.
- Type changes are gated by `PostgresDialect.can_cast_losslessly`
  (§3.5). `double` is now normalized as `double precision`; before this fix an
  unchanged `FloatField` planned an `ALTER TYPE` on every sync.
- Retired fields are gated by *declaration + `allow_drop`*, not by the
  `sys_field.state` column alone: `state` records the retirement for `doctor`
  and UI, but `_apply_drops` only ever considers names that are recorded and no
  longer declared. This keeps the safety rule independent of metadata drift.
- A nullable column added to a non-empty table is not backfilled (existing
  rows stay `NULL`); only **required** added columns get the neutral backfill
  described in §3.4. That is deliberate, not an oversight.
- `sync_dirty()` (request path) applies safe changes and logs `SchemaBlocked`
  instead of failing the request; explicit install/update still propagate it.

Verification (executed): `tests/test_schema_plan.py` (22 tests, fake cursor, no
PostgreSQL) plus a scratch-database probe covering create → idempotent →
undeclared rename (add + retire) → declared rename (`renamed_from` moves the
data) → blocked lossy type change → drop gating. A read-only plan against the
existing `J-ERP` database reported one additive change
(`add_column sys.field state`) and no blocks.


### Step 2 - trigger gating and preview (approx. 1 day) — **done**

- [x] `jerp/registry.py`: `sync_dirty()` applies additively (plus declared
      renames) only, caches the plan, logs `blocked`; `ensure_loaded()` never
      raises because of a rename.
- [x] `jerp/cli.py`: `update --dry-run`, `--allow-drop`; print plan table;
      `doctor` lists retired columns and their `DROP COLUMN` SQL.
- [x] `modules/core/models/module.py`: add `state` to `SysField`; add
      `preview` exposed method; `update(name, allow_drop=False)`.
- [x] UI: confirmation dialog with plan output (`PlanDialog` in the shared
      `Table` via a `preview` action descriptor; no view bundle change needed,
      but the runtime must be rebuilt).
- [x] `cli doctor`: list retired fields and their columns.

**Step 2 notes / deviations from the design above**

- **Declared renames run on the request path.** §3.3 and acceptance criterion 2
  say a request never renames. After Step 1 a rename only happens when the
  field declares `renamed_from`, so applying it on a request is lossless and
  keeps a renamed deploy working; blocking it would break the app until an
  operator runs `update`. The request path therefore applies declared renames
  and still blocks **all type changes** (even lossless ones, which are reported
  as deferred) and drops.
- A blocked rename now also suppresses the `add_column` for that field. Without
  this, a request-path sync would create the target column, and the operator's
  later rename could never run (the column already exists), stranding the data.
- `--allow-drop` is database-wide, not module-scoped: `Registry.update` syncs
  every built model, so module-scoping would need ownership metadata. The CLI
  and the dialog say so explicitly.
- `module.preview` validates the module name but plans the full database, which
  is exactly what `update` applies.
- A blocked `Module.update` returns `{updated: [], plan, error}` instead of a
  bare API error, so the dialog can show which changes were skipped. The safe
  part is already committed (same contract as `SchemaBlocked`).
- `SchemaSyncer.retired_fields()` reads `sys_field.state`; on a database that
  predates the column it raises a clear `RuntimeError`, so `doctor` tells the
  operator to run an update first.
- `_format_plan` is a pure function in `jerp/cli.py` and is unit-tested; it
  renders changes, blocked entries, warnings, and the destructive warning.

Verification (executed): 69 unit tests pass (`tests/test_schema_plan.py` covers
blocked renames skipping adds, request-path type deferral, `retired_fields`, and
`_format_plan`); `compileall` clean; `npm run typecheck` and `npm run build`
clean. Scratch-database probe: request path adds a column while deferring a
lossless retype, a blocked rename adds no column, `registry.preview` rejects an
unknown module, `doctor` lists the retired column and its SQL, and
`update --dry-run` succeeds. Read-only dry run against the existing `J-ERP`
database still reports only `add_column sys_field.state`; `doctor` there exits
1 with "run a module update once" because that database does not have the
column yet, and nothing was changed.

### Step 3 - versioned migrations (approx. 2-3 days)

- [ ] `jerp/migrations.py`: discovery, numeric version ordering, `migrate(cr,
      version)` contract, pre/post execution.
- [ ] `jerp/registry.py`: one transaction for pre → sync → post → `_record`;
      move `build_views` and seeds outside it.
- [ ] `jerp/modules.py`: `install`/`update` stop calling `_record` before the
      sync; `uninstall` wrapped in one transaction.
- [ ] `modules/core/configure.json`: bump version to `1.1.0` with an empty
      `migrations/1.1.0/` example? No - only add a folder when there is a real
      script; document the layout in README instead.

Verification: a scratch DB at version `1.0.0` with a test module at `1.1.0`
whose `pre` script copies a column; kill the process mid-sync; confirm the
version row is still `1.0.0` and the column layout unchanged.

### Step 4 - cycle detection and uninstall atomicity (approx. 0.5 day)

- [ ] `jerp/modules.py:97` `resolve_order`: three states
      (`visiting`/`visited`) and a clear error naming the cycle.
- [ ] `jerp/registry.py:280` `_installed_order`: same.
- [ ] `jerp/modules.py:156` `uninstall`: single transaction, `_record` removal
      last; `Registry.uninstall` runs `load()`/`init_models()` inside it.
- [ ] Tests for `A → A` and `A → B → A`.

## 5. Data migration for existing databases

- `sys_field.state` is an additive column with a default; the existing sync
  handles it. Rows that are currently `active` stay `active`, which is correct.
- No J-ERP database today has retired fields (the current code deletes them),
  so `doctor` starts empty. If an old orphan column exists from a manual
  rename, `doctor` is where it appears.
- The `_rename_from` legacy model rename (`schema.py:361`) is untouched; this
  plan only adds field-level rename metadata.

## 6. Tests

Unit tests, no PostgreSQL (new `tests/test_schema_plan.py`, plus additions to
`tests/test_fields.py`):

- `renamed_from` resolves to the declared old field, and only that one;
- two removed fields + two added fields do not pair up;
- `mode='plan'` emits descriptors and SQL and executes no DDL (fake cursor
  recording `execute` calls);
- `allow_drop=False` leaves the column and adds a `retired` entry;
- `allow_drop=True` drops only `retired` rows, never `active` ones;
- type-change classification: allow/deny matrix;
- `resolve_order` raises on self-cycle and two-node cycle;
- migration folder ordering: `1.9.0 < 1.10.0 < 2.0.0`;
- `pre` sees the old columns, `post` the new ones (fake cursor);
- installed version is unchanged when the sync raises.

Integration (manual, against a scratch database - no CI exists):

1. rows with data, rename with `renamed_from`, assert values preserved;
2. rename without the declaration, assert refused and values intact;
3. remove a field, assert column kept and listed by `doctor`;
4. drop with the flag, assert data gone;
5. uninstall `stock`, interrupt between drops (raise in a monkeypatched
   `drop_model`), assert nothing was dropped and `sys.module` still lists it.

## 7. Acceptance criteria

- No code path drops a column, renames a column, or changes a column type
  without either a declaration in the model or `allow_drop` / a migration
  script passed by an operator.
- A deploy alone (code changed, no operator action) can only add tables,
  nullable/defaulted columns, and indexes, plus renames that are explicitly
  declared with `renamed_from` (lossless by contract; see the Step 2 note).
- `jerp.cli update --dry-run` prints every operation that a subsequent apply
  would perform, with SQL, and exits non-zero when something is blocked.
- Install/update either commit schema + migrations + version together or change
  nothing.

## 8. Out of scope

- Authentication and authorization: `.agents/reviews/*` place this first; the
  open model API is a larger exposure than schema sync. Do that work before
  this plan if only one can be done this week.
- Reviewable migration *files generated from the diff* (Claude's preference).
  The runner in Step 3 gives scripts-in-the-repo; generating them belongs in a
  later iteration, after there is at least one real migration to model it on.
- `Decimal` money, domain OR/NOT, connection-pool eviction, ASGI server.

## 9. Open questions

1. Should `update(force=True)` keep re-syncing additive changes when the version
   did not move? (Proposed: yes, but it must never run migrations again.)
2. Should the UI allow `allow_drop` at all, or should drops be CLI-only?
   (Proposed: UI toggle with a typed confirmation; CLI is the escape hatch.)
3. Is a `state` column on `sys_field` preferable to a separate
   `sys_field_retired` table? (Proposed: column; one less model and the sync
   already updates that row.)
4. Do we want an `end-*` phase now? (Proposed: no, add it only when a
   multi-module data fix appears.)
