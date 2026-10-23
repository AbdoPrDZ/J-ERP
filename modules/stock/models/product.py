from jerp import fields, models


class Product(models.Model):
  _table = 'products'

  name = fields.StringField(
    name='Name',
    required=True,
  )
  image = fields.ImageField(
    name='Image',
  )
