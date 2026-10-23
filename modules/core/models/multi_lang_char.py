from jerp import fields, models


class MultiLangChar(models.Model):
  """Translation of one character field for one record and language."""

  _name = 'sys.multi_lang_char'
  _label = 'value'

  field_id = fields.Many2oneField(
    name='Field',
    comodel='sys.field',
    required=True,
    help='Model field metadata this translation belongs to.',
  )
  lang_id = fields.Many2oneField(
    name='Language',
    comodel='sys.lang',
    required=True,
    help='Language of this translation.',
  )
  res_id = fields.BigIntField(
    name='Record ID',
    required=True,
    help='ID of the record holding the translated field.',
  )
  value = fields.StringField(
    name='Value',
    required=True,
    help='Translated text.',
  )
  key = fields.StringField(
    name='Key',
    required=True,
    unique=True,
    help='Unique field/record/language identifier for this translation.',
  )
