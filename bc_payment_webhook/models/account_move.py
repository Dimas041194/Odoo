from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    x_bc_payment_notified = fields.Boolean(string="BC Payment Notified", default=False)
    x_bc_partial_payment_notified = fields.Boolean(string="BC Partial Payment Notified", default=False)
    x_bc_no_payment_notified = fields.Boolean(string="BC No Payment Notified", default=False)
