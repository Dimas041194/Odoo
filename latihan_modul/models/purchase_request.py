from odoo import models, fields, api

class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _description = 'Purchase Request'

    name = fields.Char(string='Request Reference', required=True, copy=False, readonly=True, default='New')
    request_date = fields.Date(string='Request Date', default=fields.Date.context_today)
    requested_by = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user)
    line_ids = fields.One2many('purchase.request.line', 'request_id', string='Request Lines')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'To Approve'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft')

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_create_po(self):
        PurchaseOrder = self.env['purchase.order']
        for request in self:
            po = PurchaseOrder.create({
                'partner_id': request.line_ids[0].vendor_id.id if request.line_ids else False,
                'order_line': [
                    (0, 0, {
                        'product_id': line.product_id.id,
                        'name': line.product_id.name,
                        'product_qty': line.product_qty,
                        'price_unit': line.product_id.standard_price,
                        'date_planned': fields.Date.today(),
                    }) for line in request.line_ids
                ]
            })
            request.state = 'done'
        return True

class PurchaseRequestLine(models.Model):
    _name = 'purchase.request.line'
    _description = 'Purchase Request Line'

    request_id = fields.Many2one('purchase.request', string='Purchase Request', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_qty = fields.Float(string='Quantity', required=True, default=1.0)
    vendor_id = fields.Many2one('res.partner', string='Preferred Vendor', domain=[('supplier_rank', '>', 0)])
