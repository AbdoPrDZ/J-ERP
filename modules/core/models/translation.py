from jerp import fields, models


class SysTranslation(models.Model):
  """Translated UI and metadata strings."""

  _name = 'sys.translation'
  _description = 'Translated UI and metadata strings.'
  _label = 'key'
  _track_refs = False

  lang_id = fields.Many2oneField(
    'sys.lang',
    name='Language',
    required=True,
    index=True,
    help='Language of this translation.',
  )
  module = fields.StringField(
    name='Module',
    required=True,
    index=True,
    help='Module that owns this translation key.',
  )
  key = fields.StringField(
    name='Key',
    required=True,
    index=True,
    help='Logical translation key, for example view.core.modules.title.',
  )
  code = fields.StringField(
    name='Code',
    required=True,
    unique=True,
    help='Unique language/key identifier, for example ar:view.core.modules.title.',
  )
  value = fields.TextField(
    name='Translation',
    help='Translated text. Empty values fall back to the source language.',
  )
  source = fields.SelectionField(
    name='Source',
    selection=[('file', 'File'), ('db', 'Database')],
    default='file',
    required=True,
    help='Where this value came from.',
  )
  active = fields.BooleanField(
    name='Active',
    default=True,
    help='Inactive translations are ignored at runtime.',
  )
