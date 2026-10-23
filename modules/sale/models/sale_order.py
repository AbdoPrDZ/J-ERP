from datetime import date

from jerp import fields, models
from jerp.api import api_expose, depends_on

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
    help='Reference used to identify this sales order.',
    required=True,
  )
  client_id = fields.Many2oneField(
    'sys.contact',
    name='Customer',
    help='Contact who placed this order.',
    required=True,
  )
  date_order = fields.DateField(
    name='Order date',
    help='Date on which the order was placed.',
    default=date.today,
    required=True,
  )
  state = fields.SelectionField(
    STATE_SELECTION,
    name='Status',
    help='Current step of the order: draft, confirmed, done or cancelled.',
    default='draft',
    readonly=True,
  )
  amount_total = fields.FloatField(
    name='Total',
    help='Sum of all line subtotals; calculated automatically.',
    compute='_compute_amount_total',
  )
  note = fields.TextField(
    name='Notes',
    help='Internal notes about this order.',
  )

  @depends_on(['lines.subtotal'])
  def _compute_amount_total(self):
    for order in self:
      order.amount_total = sum(line.subtotal for line in order.lines)

  @api_expose
  def confirm(self):
    self.is_one() # raise error if not exactly one record

    self.state = 'confirmed'
    return True

  @api_expose
  def done(self):
    self.is_one()

    self.state = 'done'

    return True

  @api_expose
  def cancel(self):
    self.is_one()

    self.state = 'cancelled'

    return True

  @api_expose
  def reset_to_draft(self):
    self.is_one()

    self.state = 'draft'

    return True
