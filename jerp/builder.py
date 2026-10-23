"""Model build engine.

Collects the model sources installed in one database and combines them into a
single built class per model name:

* a base model owns the table and its fields
* ``_inherit`` sources add fields / methods to an existing model
* ``_inherits`` sources create a new model by copying fields from other models

The builder is per database: two databases with different installed modules get
different built classes. Built classes are never registered in
:class:`jerp.models.ModelRegistry`; they are handed to the per-database
:class:`jerp.registry.Registry`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Mapping

from jerp.models import ModelMeta

#: Columns supplied by ``BaseModel``; contributions never redefine them.
STANDARD_FIELD_NAMES = ('id', 'created_at', 'updated_at')


@dataclass
class BuildResult:
  models: dict[str, type]
  sources: dict[str, list]
  fingerprints: dict[str, str]
  changed: set[str]


def _label(source) -> str:
  return f'{source.__module__}.{source.__qualname__}'


def _field_signature(field) -> tuple:
  default = field.default
  if callable(default):
    default = getattr(default, '__qualname__', repr(default))

  try:
    column_type = field.column_type()
  except Exception:  # pragma: no cover - defensive for custom fields
    column_type = field.ttype

  return (
    field.attr_name,
    field.column_name,
    column_type,
    bool(field.required),
    bool(field.readonly),
    bool(field.hide),
    bool(field.unique),
    bool(field.index),
    bool(field.primary_key),
    bool(field.auto_increment),
    bool(getattr(field, 'multi_language', False)),
    repr(default),
    repr(getattr(field, 'selection', None)),
    repr(getattr(field, 'comodel', None)),
  )


class ModelBuilder:
  """Builds one effective model class per model name for a database."""

  def __init__(self):
    self._cache: dict[str, tuple[str, type]] = {}
    self._result: BuildResult | None = None

  # --- public API ---------------------------------------------------------

  def build(
    self,
    modules: Mapping[str, Iterable[type]],
    depends: Mapping[str, Iterable[str]] | None = None,
  ) -> BuildResult:
    """Build models from ``modules`` (an ordered module -> model sources map).

    ``modules`` must follow dependency order. ``depends`` maps module names to
    their declared dependencies and is used for validation.
    """

    self._result = None
    depends = depends or {}

    bases, new_models, extensions = self._collect(modules)
    nodes = {**bases, **new_models}

    self._validate_targets(nodes, extensions)
    self._validate_dependencies(modules, nodes, extensions, depends)

    order = self._build_order(nodes)

    built: dict[str, type] = {}
    sources: dict[str, list] = {}
    fingerprints: dict[str, str] = {}
    changed: set[str] = set()

    for name in order:
      owner, source = nodes[name]
      exts = [model for _module, model in extensions.get(name, ())]
      parents = [
        built[parent]
        for parent in getattr(source, '_inherits', ()) or ()
      ]
      parents = self._maximal(parents)

      if getattr(source, '_virtual', False) and (parents or exts):
        raise ValueError(
          f"Model '{name}' is virtual and cannot be extended or used as an "
          f"_inherits parent."
        )
      if parents and any(getattr(parent, '_virtual', False) for parent in parents):
        raise ValueError(
          f"Model '{name}': _inherits cannot use a virtual model as a parent."
        )

      built_class, ordered, source_order = self._compose(
        source, exts, parents, name
      )
      fingerprint = self._fingerprint(
        name, source, exts, parents, ordered, fingerprints
      )

      cached = self._cache.get(name)
      if cached is not None and cached[0] == fingerprint:
        built[name] = cached[1]
      else:
        self._cache[name] = (fingerprint, built_class)
        built[name] = built_class
        changed.add(name)

      fingerprints[name] = fingerprint
      sources[name] = source_order

    self._result = BuildResult(
      models=built,
      sources=sources,
      fingerprints=fingerprints,
      changed=changed,
    )
    return self._result

  def describe(self, name: str) -> dict | None:
    """Introspection for a built model, or ``None`` if it is not built."""

    if self._result is None or name not in self._result.models:
      return None

    model = self._result.models[name]
    return {
      'model': name,
      'table': model._table,
      'sources': [_label(source) for source in self._result.sources[name]],
      'fields': model.field_schema(),
      'api_methods': sorted((getattr(model, '_api_methods', {}) or {}).keys()),
    }

  def reset(self) -> None:
    self._cache.clear()
    self._result = None

  # --- source collection --------------------------------------------------

  def _collect(self, modules: Mapping[str, Iterable[type]]):
    bases: dict[str, tuple[str, type]] = {}
    new_models: dict[str, tuple[str, type]] = {}
    extensions: dict[str, list[tuple[str, type]]] = {}

    for module_name, models in modules.items():
      for model in models:
        if getattr(model, '_is_extension', False):
          extensions.setdefault(model._extends, []).append((module_name, model))
          continue

        target = new_models if getattr(model, '_is_inherited', False) else bases
        existing = bases.get(model._name) or new_models.get(model._name)
        if existing is not None and existing[1] is not model:
          raise ValueError(
            f"Duplicate model '{model._name}' in modules "
            f"'{existing[0]}' and '{module_name}'."
          )
        target[model._name] = (module_name, model)

    return bases, new_models, extensions

  # --- validation ---------------------------------------------------------

  def _validate_targets(self, nodes, extensions) -> None:
    for target, contributors in extensions.items():
      if target not in nodes:
        labels = ', '.join(_label(model) for _module, model in contributors)
        raise ValueError(
          f"_inherit target '{target}' is not available in this database "
          f"(from {labels}). Install the module that declares the base model."
        )

  def _validate_dependencies(self, modules, nodes, extensions, depends) -> None:
    owners = {
      name: module_name for name, (module_name, _source) in nodes.items()
    }
    closures: dict[str, set[str]] = {}

    def closure(module_name: str) -> set[str]:
      if module_name not in closures:
        closures[module_name] = self._module_closure(module_name, depends)
      return closures[module_name]

    def require(module_name: str, owner: str, model, what: str) -> None:
      if owner == module_name:
        return
      if owner not in closure(module_name):
        raise ValueError(
          f"Module '{module_name}' uses {what} from module '{owner}' "
          f"(model '{model._name}'), but '{owner}' is not in its dependencies. "
          f"Add \"{owner}\" to depends in modules/{module_name}/configure.json."
        )

    for module_name, models in modules.items():
      for model in models:
        if getattr(model, '_is_extension', False):
          target = model._extends
          owner = owners.get(target)
          if owner is not None:
            require(module_name, owner, model, f"_inherit = '{target}'")
        elif getattr(model, '_is_inherited', False):
          for parent in model._inherits:
            owner = owners.get(parent)
            if owner is not None:
              require(module_name, owner, model, f"_inherits parent '{parent}'")

  @staticmethod
  def _module_closure(module_name: str, depends) -> set[str]:
    seen: set[str] = set()

    def visit(name: str) -> None:
      if name in seen:
        return
      seen.add(name)
      for dependency in depends.get(name, ()) or ():
        visit(dependency)

    visit(module_name)
    return seen

  # --- build order --------------------------------------------------------

  def _build_order(self, nodes) -> list[str]:
    order: list[str] = []
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(name: str) -> None:
      if name in done:
        return
      if name in visiting:
        raise ValueError(
          f"Circular _inherits dependency detected at model '{name}'."
        )

      visiting.add(name)
      _module, source = nodes[name]
      for parent in getattr(source, '_inherits', ()) or ():
        if parent not in nodes:
          raise ValueError(
            f"Model '{name}': _inherits parent '{parent}' is not available "
            f"in this database."
          )
        visit(parent)
      visiting.discard(name)
      done.add(name)
      order.append(name)

    for name in nodes:
      visit(name)
    return order

  # --- composition --------------------------------------------------------

  def _compose(self, source, exts, parents, name):
    source_order = [source, *parents, *exts]
    groups: list[tuple[str, list[tuple[str, object]]]] = []

    for parent in parents:
      groups.append((_label(parent), list(parent._fields.items())))

    groups.append((
      _label(source),
      [
        (field_name, field)
        for field_name, field in source._fields.items()
        if not parents or field_name not in STANDARD_FIELD_NAMES
      ],
    ))

    for ext in exts:
      groups.append((
        _label(ext),
        [
          (field_name, field)
          for field_name, field in ext._fields.items()
          if field_name not in STANDARD_FIELD_NAMES
        ],
      ))

    ordered = self._merge_fields(name, groups)

    table = source._table
    attrs = {
      '_name': name,
      '_table': table,
      '_label': getattr(source, '_label', None),
      '_views': dict(getattr(source, '_views', {}) or {}),
      '_virtual': bool(getattr(source, '_virtual', False)),
      '_composed': True,
      '_sources': tuple(source_order),
    }

    # Methods: extensions override the model they extend; the model overrides
    # its _inherits parents. MRO is the source of precedence.
    bases = tuple(exts) + (source,) + tuple(parents)
    built = ModelMeta(f'{source.__name__}Built', bases, attrs)
    built._fields = ordered
    built._inherits = tuple(getattr(source, '_inherits', ()) or ())
    built._field_sources = {
      field_name: label
      for label, items in groups
      for field_name, _field in items
    }
    built._extension_fields = frozenset(
      field_name
      for ext in exts
      for field_name in ext._fields
      if field_name not in STANDARD_FIELD_NAMES
    )
    return built, ordered, source_order

  @staticmethod
  def _merge_fields(name: str, groups) -> dict:
    ordered: dict = {}
    columns: dict = {}

    for label, items in groups:
      for field_name, field in items:
        if field_name in STANDARD_FIELD_NAMES and field_name in ordered:
          continue

        existing = ordered.get(field_name)
        if existing is not None:
          if existing is field:
            continue
          raise ValueError(
            f"Model '{name}': field '{field_name}' is declared twice "
            f"(second declaration in {label})."
          )

        column = field.column_name
        existing_column = columns.get(column)
        if existing_column is not None and existing_column is not field:
          raise ValueError(
            f"Model '{name}': column '{column}' is used by more than one "
            f"field (conflict in {label})."
          )

        ordered[field_name] = field
        columns[column] = field

    return ordered

  @staticmethod
  def _maximal(classes: list[type]) -> list[type]:
    """Drop parents that are already ancestors of another parent."""

    unique: list[type] = []
    for candidate in classes:
      if candidate not in unique:
        unique.append(candidate)

    return [
      candidate
      for candidate in unique
      if not any(
        other is not candidate and issubclass(other, candidate)
        for other in unique
      )
    ]

  def _fingerprint(
    self,
    name: str,
    source,
    exts,
    parents,
    ordered,
    fingerprints: Mapping[str, str],
  ) -> str:
    payload = {
      'model': name,
      'table': source._table,
      'virtual': bool(getattr(source, '_virtual', False)),
      'sources': [_label(item) for item in (source, *parents, *exts)],
      'source_ids': [id(item) for item in (source, *parents, *exts)],
      'fields': [
        (field_name, _field_signature(field))
        for field_name, field in ordered.items()
      ],
      'parents': [
        (parent._name, fingerprints.get(parent._name))
        for parent in parents
      ],
      'extensions': [_label(ext) for ext in exts],
    }
    return hashlib.sha256(repr(payload).encode('utf-8')).hexdigest()
