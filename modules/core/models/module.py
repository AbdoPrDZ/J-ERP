from jerp import fields
from jerp.api import api_expose
from jerp.env import Environment
from jerp.models import Model


class SysModule(Model):
  """Installed modules and their versions, per database."""

  _name = 'sys.module'
  _table = 'sys_module'

  name = fields.StringField(name='Name', required=True, unique=True)
  version = fields.StringField(name='Version')
  state = fields.StringField(name='State', default='installed')
  summary = fields.TextField(name='Summary')


class SysModel(Model):
  """Models that have been synchronized into this database."""

  _name = 'sys.model'
  _table = 'sys_model'

  name = fields.StringField(name='Model', required=True, unique=True)
  table_name = fields.StringField(name='Table')


class SysField(Model):
  """Field to column mapping, used for deterministic rename detection."""

  _name = 'sys.field'
  _table = 'sys_field'

  model = fields.StringField(name='Model', required=True, index=True)
  field_name = fields.StringField(name='Field', required=True)
  column_name = fields.StringField(name='Column', required=True)
  ttype = fields.StringField(name='Type')
  label = fields.StringField(name='Label')


class Module(Model):
  """Virtual model over the modules discovered on disk (no table)."""

  _name = 'module'
  _virtual = True

  name = fields.StringField(name='Name')
  version = fields.StringField(name='Version')
  state = fields.StringField(name='Status')
  summary = fields.TextField(name='Description')
  depends = fields.StringField(name='Depends')

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
  @api_expose
  def all(cls, domain=None, fields=None, order=None, limit=None, offset=None):
    return cls._records()

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
