from jerp import fields, models


class State(models.Model):
  """State/province reference data."""

  _name = 'sys.state'
  _description = 'States or provinces belonging to a country.'
  _label = 'name'

  name = fields.StringField(
    name='Name',
    required=True,
    help='State, province or wilaya name.',
  )
  code = fields.StringField(
    name='Code',
    size=10,
    help='Administrative code used for this state.',
  )
  country_id = fields.Many2oneField(
    name='Country',
    comodel='sys.country',
    required=True,
    help='Country this state belongs to.',
  )
