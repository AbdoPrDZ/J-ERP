from jerp import fields, models
from jerp.env import Environment


class SaleOrderLine(models.Model):
  """A product line on a sales order."""

  _name = 'sale.order.line'
  _label = 'name'

  order_id = fields.Many2oneField(
    name='Order',
    comodel='sale.order',
    required=True,
    help='Sales order this line belongs to.',
  )
  product_id = fields.Many2oneField(
    name='Product',
    comodel='stock.product',
    required=True,
    help='Product sold on this line.',
  )
  name = fields.StringField(
    name='Description',
    required=True,
    help='Text shown for this line on the order.',
  )
  quantity = fields.FloatField(
    name='Quantity',
    default=1.0,
    required=True,
    help='Number of units ordered.',
  )
  price_unit = fields.FloatField(
    name='Unit price',
    default=0.0,
    required=True,
    help='Selling price for one unit.',
  )
  subtotal = fields.FloatField(
    name='Subtotal',
    default=0.0,
    readonly=True,
    help='Quantity multiplied by unit price; calculated automatically.',
  )

  # --- totals -------------------------------------------------------------

  @classmethod
  def _refresh_order(cls, order_id):
    if not order_id:
      return
    SaleOrder = Environment.instance.registry().get('sale.order')
    if SaleOrder is not None:
      SaleOrder.recalculate_total(order_id)

  @staticmethod
  def _subtotal(quantity, price) -> float:
    return float(quantity or 0.0) * float(price or 0.0)

  @classmethod
  def temp_values(cls, values) -> dict:
    values = dict(values)
    quantity = values.get('quantity')
    if quantity is None:
      quantity = cls._fields['quantity'].default or 0.0
    price = values.get('price_unit')
    if price is None:
      price = cls._fields['price_unit'].default or 0.0
    values['subtotal'] = cls._subtotal(quantity, price)
    return values

  # --- CRUD overrides -----------------------------------------------------

  @classmethod
  def create(cls, **values):
    quantity = values.get('quantity')
    if quantity is None:
      quantity = cls._fields['quantity'].default or 0.0
    price = values.get('price_unit')
    if price is None:
      price = cls._fields['price_unit'].default or 0.0

    values['subtotal'] = cls._subtotal(quantity, price)
    record = super().create(**values)
    type(record)._refresh_order(record.order_id)
    return record

  def write(self, values) -> bool:
    values = dict(values)
    old_order = self.order_id

    if 'quantity' in values or 'price_unit' in values:
      quantity = values.get('quantity', self.quantity)
      price = values.get('price_unit', self.price_unit)
      values['subtotal'] = self._subtotal(quantity, price)

    result = super().write(values)
    type(self)._refresh_order(old_order)
    if self.order_id != old_order:
      type(self)._refresh_order(self.order_id)
    return result

  def unlink(self) -> bool:
    order_id = self.order_id
    result = super().unlink()
    type(self)._refresh_order(order_id)
    return result
