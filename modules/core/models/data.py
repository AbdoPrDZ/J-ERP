from jerp import fields, models


class SysData(models.Model):
  """External identifiers for records (similar to Odoo XML IDs)."""

  _name = 'sys.data'
  _label = 'key'
  _track_refs = False

  module = fields.StringField(
    name='Module',
    required=True,
    help='Module that owns this external identifier.',
  )
  model = fields.StringField(
    name='Model',
    required=True,
    help='Model name of the referenced record.',
  )
  name = fields.StringField(
    name='Name',
    required=True,
    help='Short key name, without the module prefix.',
  )
  key = fields.StringField(
    name='Key',
    required=True,
    unique=True,
    help='Full unique external identifier used by env.ref().',
  )
  res_id = fields.BigIntField(
    name='Record ID',
    required=True,
    help='ID of the referenced record.',
  )
