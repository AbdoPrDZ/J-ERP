from jerp import fields, models
from jerp.api import on_change, depends_on


class SaleOrderLine(models.Model):
  """A product line on a sales order."""

  _name = 'sale.order.line'
  _label = 'name'

  order_id = fields.Many2oneField(
    'sale.order',
    name='Order',
    help='Sales order this line belongs to.',
    required=True,
  )
  product_id = fields.Many2oneField(
    'stock.product',
    name='Product',
    help='Product sold on this line.',
    required=True,
  )
  name = fields.StringField(
    name='Description',
    help='Text shown for this line on the order.',
    required=True,
  )
  quantity = fields.FloatField(
    name='Quantity',
    help='Number of units ordered.',
    default=1.0,
    required=True,
  )
  standard_price = fields.FloatField(
    name='Cost',
    help='Cost of one unit.',
    required=True,
    readonly=True,
  )
  price_unit = fields.FloatField(
    name='Unit price',
    help='Selling price for one unit.',
  )
  subtotal = fields.FloatField(
    name='Subtotal',
    help='Quantity multiplied by unit price; calculated automatically.',
    compute='_compute_subtotal',
  )
  margin = fields.FloatField(
    name='Margin',
    help='Profit margin for this line, as a percentage of the unit price; calculated automatically.',
    compute='_compute_margin',
  )

  @on_change(['product_id'])
  def _on_change_product_id(self):
    for line in self:
      line.name = line.product_id.name  if line.product_id else ""
      line.standard_price = line.product_id.standard_price  if line.product_id else 0.0
      line.price_unit = line.product_id.price  if line.product_id else 0.0

  @depends_on(['quantity', 'price_unit'])
  def _compute_subtotal(self):
    for line in self:
      line.subtotal = float(line.quantity) * float(line.price_unit)
