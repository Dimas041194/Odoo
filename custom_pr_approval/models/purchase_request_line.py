from odoo import models, fields

class PurchaseRequestLine(models.Model):
    _name = 'custom.purchase.request.line'
    _description = 'Purchase Request Line'

    pr_id = fields.Many2one('custom.purchase.request', string='Purchase Request', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_qty = fields.Float(string='Quantity', required=True, default=1.0)
    price_unit = fields.Float(string='Unit Price', required=True)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    price_subtotal = fields.Monetary(string='Subtotal', compute='_compute_subtotal', store=True)
    currency_id = fields.Many2one(related='pr_id.currency_id', store=True, readonly=True)

    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.product_qty * line.price_unit
