from jerp import fields, models


class Country(models.Model):
  """Country reference data."""

  _name = 'sys.country'
  _description = 'Countries and related reference data.'
  _label = 'name'

  name = fields.StringField(
    name='Name',
    required=True,
    multi_language=True,
    help='Country name; use the Translations button for other languages.',
  )
  code = fields.StringField(
    name='Code',
    size=2,
    required=True,
    unique=True,
    help='Two-letter ISO country code, for example DZ or US.',
  )
  phone_code = fields.StringField(
    name='Phone Code',
    size=10,
    help='International dialing prefix, for example 213 or 1.',
  )
