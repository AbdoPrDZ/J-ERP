from jerp import fields, models


class Contact(models.Model):
  """Person/contact record (similar to Odoo's ``res.partner``)."""

  _name = 'sys.contact'
  _label = 'name'

  name = fields.StringField(
    name='Name',
    required=True,
    help='Full name of the person or contact.',
  )
  email = fields.StringField(
    name='Email',
    required=True,
    help='Primary email address.',
  )
  phone = fields.StringField(
    name='Phone',
    required=True,
    help='Primary phone number, including country code if possible.',
  )
  address = fields.StringField(
    name='Address',
    required=True,
    help='Street address and any additional location details.',
  )
  country_id = fields.Many2oneField(
    name='Country',
    comodel='sys.country',
    help='Country where this contact is located.',
  )
  state_id = fields.Many2oneField(
    name='State',
    comodel='sys.state',
    help='State or province where this contact is located.',
  )
