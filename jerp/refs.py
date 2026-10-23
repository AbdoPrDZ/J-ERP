"""External record references (``sys.data``)."""

from __future__ import annotations


def model_module(model) -> str:
  """The owning module name for a model source/built class."""

  sources = getattr(model, '_sources', None)
  source = sources[0] if sources else model
  module_path = getattr(source, '__module__', '') or ''
  parts = module_path.split('.')
  if len(parts) >= 2 and parts[0] == 'modules':
    return parts[1]
  return parts[0] if parts and parts[0] else 'jerp'


def resolve_key(module: str, model_name: str, raw_key: str) -> tuple[str, str]:
  """Return ``(full_key, short_name)``.

  A fully qualified key starting with ``<module>.`` is kept; a plain name is
  expanded to ``<module>.<model_name>.<name>``.
  """

  raw_key = str(raw_key).strip()
  prefix = f'{module}.'
  if raw_key.startswith(prefix):
    return raw_key, raw_key[len(prefix):]
  return f'{module}.{model_name}.{raw_key}', raw_key


def backfill(registry) -> int:
  """Create an external id for every existing record that has none."""

  Data = registry.get('sys.data')
  if Data is None:
    return 0

  created = 0
  for model_name, model in registry.models.items():
    if model_name == 'sys.data':
      continue
    if getattr(model, '_virtual', False) or not getattr(model, '_track_refs', True):
      continue

    records = model.search([], order='id')
    if not records:
      continue

    refs = Data.search([('model', '=', model_name)])
    referenced = {int(ref.res_id) for ref in refs}
    for record in records:
      record_id = int(record.id)
      if record_id in referenced:
        continue
      model.register_ref(record_id)
      created += 1

  return created
