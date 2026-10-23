from jerp import fields
from jerp.api import api_expose
from jerp.env import Environment
from jerp.models import Model


class SysModule(Model):
  """Installed modules and their versions, per database."""

  _name = 'sys.module'

  name = fields.StringField(
    name='Name',
    required=True,
    unique=True,
    help='Technical module name.',
  )
  version = fields.StringField(
    name='Version',
    help='Installed module version.',
  )
  state = fields.SelectionField(
    name='Status',
    selection=[
      ('installed', 'Installed'),
      ('install_failed', 'Install Failed'),
      ('not_installed', 'Not Installed'),
    ],
    help='Whether the module is installed in this database.',
  )
  summary = fields.TextField(
    name='Summary',
    help='Short description of the module.',
  )


class SysModel(Model):
  """Models that have been synchronized into this database."""

  _name = 'sys.model'

  name = fields.StringField(
    name='Model',
    required=True,
    unique=True,
    help='Logical model name.',
  )
  table_name = fields.StringField(
    name='Table',
    help='Physical database table for this model.',
  )


class SysField(Model):
  """Field to column mapping, used for deterministic rename detection."""

  _name = 'sys.field'

  model = fields.StringField(
    name='Model',
    required=True,
    help='Model that owns this field.',
  )
  field_name = fields.StringField(
    name='Field',
    required=True,
    help='Python field name on the model.',
  )
  column_name = fields.StringField(
    name='Column',
    required=True,
    help='Physical database column name.',
  )
  ttype = fields.StringField(
    name='Type',
    help='Framework field type.',
  )
  label = fields.StringField(
    name='Label',
    help='Human-readable field label.',
  )


class Module(Model):
  """Virtual model over the modules discovered on disk (no table)."""

  _name = 'module'
  _virtual = True

  name = fields.StringField(name='Name', help='Module technical name.')
  version = fields.StringField(name='Version', help='Module version.')
  state = fields.StringField(
    name='Status',
    help='Whether the module is installed in this database.',
  )
  summary = fields.TextField(
    name='Description',
    help='Short module description.',
  )
  depends = fields.StringField(
    name='Depends',
    help='Comma-separated modules this module depends on.',
  )

  @classmethod
  def _records(cls) -> list[dict]:
    registry = Environment.instance.registry()
    manager = registry.module_manager
    discovered = manager.discover()
    installed = manager.installed()

    records = []
    for name, info in sorted(discovered.items()):
      is_installed = name in installed
      actions = []
      if is_installed:
        actions.append({'label': 'Update', 'method': 'update', 'key': 'name'})
        if name != 'core':
          actions.append(
            {'label': 'Uninstall', 'method': 'uninstall', 'key': 'name',
             'style': 'danger'}
          )
      else:
        actions.append(
          {'label': 'Install', 'method': 'install', 'key': 'name',
           'style': 'primary'}
        )
      record = {
        'id': name,
        'name': name,
        'version': info.version,
        'state': 'installed' if is_installed else 'not installed',
        'summary': info.summary,
        'depends': ', '.join(info.depends) or '—',
        'logo': info.logo,
        '_actions': actions,
      }
      record['_label'] = cls.display_name(record)
      records.append(record)
    return records

  @classmethod
  def _sorted_records(cls, order=None) -> list[dict]:
    records = cls._records()
    if not order:
      return records

    specs = (
      [part.strip() for part in order.split(',') if part.strip()]
      if isinstance(order, str)
      else list(order)
    )
    for spec in reversed(specs):
      tokens = spec.split()
      if not tokens:
        continue
      name = tokens[0]
      reverse = len(tokens) > 1 and tokens[1].lower() == 'desc'
      records.sort(
        key=lambda record: str(record.get(name, '') or ''),
        reverse=reverse,
      )
    return records

  @classmethod
  @api_expose
  def all(cls, domain=None, fields=None, order=None, limit=None, offset=None):
    records = cls._sorted_records(order)
    start = int(offset) if offset else 0
    if start:
      records = records[start:]
    if limit is not None:
      records = records[:int(limit)]
    return records

  @classmethod
  @api_expose
  def count(cls, domain=None) -> int:
    return len(cls._records())

  @classmethod
  @api_expose
  def find(cls, id, fields=None):
    """A single module record (``id`` is the module name)."""

    for record in cls._records():
      if str(record['id']) == str(id):
        return record
    return None

  @classmethod
  @api_expose
  def install(cls, name: str):
    return {'installed': Environment.instance.registry().install(name)}

  @classmethod
  @api_expose
  def update(cls, name: str):
    return {'updated': Environment.instance.registry().update(name)}

  @classmethod
  @api_expose
  def uninstall(cls, name: str):
    Environment.instance.registry().uninstall(name)
    return {'uninstalled': name}
