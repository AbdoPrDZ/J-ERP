from jerp import fields, models


class Product(models.Model):
  _name = 'stock.product'
  _description = 'Products available for sale and stock.'
  _rename_from = 'product'
  _label = 'name'

  name = fields.StringField(
    name='Name',
    required=True,
    help='Product name shown in lists and on order lines.',
  )
  image = fields.ImageField(
    name='Image',
    help='Optional picture used to identify the product.',
  )
  standard_price = fields.FloatField(
    name='Standard Price',
    required=True,
    help='Internal cost price used for valuation.',
  )
  price = fields.FloatField(
    name='Price',
    required=True,
    help='Default selling price before taxes.',
  )
