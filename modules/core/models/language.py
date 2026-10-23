from jerp import fields, models


class Language(models.Model):
  """Available UI/content languages."""

  _name = 'sys.lang'
  _label = 'name'

  name = fields.StringField(
    name='Name',
    required=True,
    help='Human-readable language name, for example English.',
  )
  code = fields.StringField(
    name='Code',
    size=10,
    required=True,
    unique=True,
    help='Language code, for example en, fr or ar.',
  )
  active = fields.BooleanField(
    name='Active',
    default=True,
    help='Inactive languages are hidden from translation pickers.',
  )
  is_default = fields.BooleanField(
    name='Default',
    help='Use this language as the default value of multi-language fields.',
  )
