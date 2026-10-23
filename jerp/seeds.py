"""Idempotent module seed data loader.

A module can declare seed files in ``configure.json``::

  "seed": {
    "sys.country": {"file": "seed/country.json", "key": ["code"]},
    "sys.state": {"file": "seed/state.json", "key": ["country_id", "code"]}
  }

Each file contains a list of records using model field names. Many2one values
may be an id, a natural-key string, or a lookup object such as
``{"code": "DZ"}``. Records are created only when their key does not already
exist, so applying a module seed repeatedly is safe.
"""

from __future__ import annotations

import json
from pathlib import Path

from jerp.fields import Many2oneField


class SeedLoader:
  def __init__(self, registry):
    self.registry = registry

  def apply(self, info) -> int:
    if not info.seed:
      return 0

    created = 0
    for model_name, spec in info.seed.items():
      model = self.registry.get(model_name)
      if model is None:
        raise ValueError(
          f"[{info.name}] seed target model '{model_name}' is not installed."
        )

      file_name, configured_keys = self._parse_spec(spec)
      path = Path(info.path) / file_name
      if not path.is_file():
        raise ValueError(
          f"[{info.name}] seed file '{file_name}' for '{model_name}' was not found."
        )

      try:
        records = json.loads(path.read_text(encoding='utf-8'))
      except ValueError as exc:
        raise ValueError(
          f"[{info.name}] seed file '{file_name}' is not valid JSON: {exc}"
        ) from exc

      if not isinstance(records, list):
        raise ValueError(
          f"[{info.name}] seed file '{file_name}' must contain a list."
        )

      key_fields = (
        configured_keys
        if configured_keys is not None
        else self._default_keys(model)
      )

      for index, raw in enumerate(records):
        if not isinstance(raw, dict):
          raise ValueError(
            f"[{info.name}] seed '{file_name}' record {index + 1} must be an object."
          )

        record_values = dict(raw)
        raw_key = record_values.pop('_key', None)
        if '_translations' in record_values:
          raise ValueError(
            f"[{info.name}] seed '{file_name}' record {index + 1}: use a "
            f"multi-language dict as the field value instead of _translations."
          )
        values = self._resolve_relations(
          model, record_values, info, file_name, index
        )
        self._check_keys(values, key_fields, info, file_name, index)

        multi_values = {
          name: value
          for name, value in values.items()
          if isinstance(value, dict)
          and getattr(model._fields.get(name), 'multi_language', False)
        }

        record = None
        if key_fields:
          domain = [(name, '=', values[name]) for name in key_fields]
          rows = model.search(domain, limit=1)
          if rows:
            record = rows[0]

        if record is None:
          if raw_key not in (None, ''):
            record = model.create(
              _key=raw_key,
              _ref_module=info.name,
              **values,
            )
          else:
            record = model.create(**values)
          created += 1
        else:
          if raw_key not in (None, ''):
            model.register_ref(record.id, raw_key, module=info.name)
          else:
            # Existing records created before external ids were enabled.
            model.register_ref(record.id)
          if multi_values:
            record.write(multi_values)

    return created

  # --- helpers ------------------------------------------------------------

  @staticmethod
  def _parse_spec(spec):
    if isinstance(spec, str):
      return spec, None
    if not isinstance(spec, dict):
      raise ValueError(f'Invalid seed specification: {spec!r}')

    file_name = spec.get('file')
    if not isinstance(file_name, str) or not file_name:
      raise ValueError(f'Seed specification has no file: {spec!r}')

    key = spec.get('key')
    if key is None:
      return file_name, None
    if isinstance(key, str):
      return file_name, [key]
    return file_name, list(key)

  @staticmethod
  def _default_keys(model) -> list[str]:
    if 'code' in model._fields:
      return ['code']
    if 'name' in model._fields:
      return ['name']
    return []

  def _resolve_relations(self, model, values, info, file_name, index):
    for field_name, value in list(values.items()):
      field = model._fields.get(field_name)
      if not isinstance(field, Many2oneField):
        continue

      related = self.registry.get(field.comodel)
      if related is None:
        raise ValueError(
          f"[{info.name}] seed '{file_name}' record {index + 1} references "
          f"unknown model '{field.comodel}'."
        )

      if isinstance(value, dict):
        domain = [(key, '=', item) for key, item in value.items()]
      elif isinstance(value, str):
        if 'code' in related._fields:
          domain = [('code', '=', value)]
        elif 'name' in related._fields:
          domain = [('name', '=', value)]
        else:
          raise ValueError(
            f"[{info.name}] seed '{file_name}' record {index + 1} cannot "
            f"resolve '{value}' for '{field_name}'."
          )
      else:
        # An integer is already a record id.
        continue

      rows = related.search(domain, limit=1)
      if not rows:
        raise ValueError(
          f"[{info.name}] seed '{file_name}' record {index + 1} could not "
          f"find {field.comodel} matching {value!r}."
        )
      values[field_name] = rows[0].id

    return values

  @staticmethod
  def _check_keys(values, key_fields, info, file_name, index):
    missing = [name for name in key_fields if name not in values]
    if missing:
      raise ValueError(
        f"[{info.name}] seed '{file_name}' record {index + 1} is missing "
        f"key field(s): {', '.join(missing)}."
      )
