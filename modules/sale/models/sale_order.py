from datetime import date

from jerp import fields, models
from jerp.api import api_expose
from jerp.env import Environment

STATE_SELECTION = [
  ('draft', 'Draft'),
  ('confirmed', 'Confirmed'),
  ('done', 'Done'),
  ('cancelled', 'Cancelled'),
]


class SaleOrder(models.Model):
  """A customer sales order.

  Lines live in ``sale.order.line``; the order stores the computed total.
  """

  _name = 'sale.order'
  _label = 'name'

  name = fields.StringField(
    name='Order',
    required=True,
    help='Reference used to identify this sales order.',
  )
  client_id = fields.Many2oneField(
    name='Customer',
    comodel='sys.contact',
    required=True,
    help='Contact who placed this order.',
  )
  date_order = fields.DateField(
    name='Order date',
    default=date.today,
    required=True,
    help='Date on which the order was placed.',
  )
  state = fields.SelectionField(
    name='Status',
    selection=STATE_SELECTION,
    default='draft',
    required=True,
    help='Current step of the order: draft, confirmed, done or cancelled.',
  )
  amount_total = fields.FloatField(
    name='Total',
    default=0.0,
    readonly=True,
    help='Sum of all line subtotals; calculated automatically.',
  )
  note = fields.TextField(
    name='Notes',
    help='Internal notes about this order.',
  )

  # --- state --------------------------------------------------------------

  @classmethod
  def _set_state(cls, order_id, state: str):
    orders = cls.browse(order_id)
    if not orders:
      return None
    orders[0].write({'state': state})
    return cls.find(order_id)

  @classmethod
  @api_expose
  def confirm(cls, id):
    return cls._set_state(id, 'confirmed')

  @classmethod
  @api_expose
  def done(cls, id):
    return cls._set_state(id, 'done')

  @classmethod
  @api_expose
  def cancel(cls, id):
    return cls._set_state(id, 'cancelled')

  @classmethod
  @api_expose
  def reset_to_draft(cls, id):
    return cls._set_state(id, 'draft')

  # --- totals -------------------------------------------------------------

  @classmethod
  def recalculate_total(cls, order_id):
    """Recompute ``amount_total`` from the order's lines."""

    if not order_id:
      return None

    Line = Environment.instance.registry().get('sale.order.line')
    if Line is None:
      return None

    lines = Line.search([('order_id', '=', int(order_id))])
    total = sum(float(line.subtotal or 0.0) for line in lines)

    orders = cls.browse(order_id)
    if orders:
      orders[0].write({'amount_total': total})
    return total

  @classmethod
  @api_expose
  def lines(cls, id):
    """Order lines as API-friendly dictionaries."""

    Line = Environment.instance.registry().get('sale.order.line')
    if Line is None:
      return []
    return Line.all(domain=[('order_id', '=', int(id))], order='id')
