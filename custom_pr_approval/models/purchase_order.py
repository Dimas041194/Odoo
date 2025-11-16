from odoo import models, fields
from odoo.exceptions import UserError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    pr_id = fields.Many2one('custom.purchase.request', string='Purchase Request')

    def button_confirm(self):
        for po in self:
            if po.pr_id and po.pr_id.approval_state != 'po_created':
                raise UserError("PR terkait belum selesai approval dan pembuatan PO.")
        return super().button_confirm()
