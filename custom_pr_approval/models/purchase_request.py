from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

class PurchaseRequest(models.Model):
    _name = 'custom.purchase.request'
    _description = 'Purchase Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    user_id = fields.Many2one('res.users', string='Requester', default=lambda self: self.env.user, tracking=True)
    date_request = fields.Date(string='Request Date', default=fields.Date.context_today, tracking=True)
    line_ids = fields.One2many('custom.purchase.request.line', 'pr_id', string='Request Lines', tracking=True)
    amount_total = fields.Monetary(string='Total', compute='_compute_amount_total', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    approval_state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('po_created', 'PO Created'),
    ], default='draft', string='Approval Status', tracking=True)
    note = fields.Text(string='Notes')
    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order', readonly=True)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('custom.purchase.request') or 'New'
        return super().create(vals)

    @api.depends('line_ids.price_subtotal')
    def _compute_amount_total(self):
        for pr in self:
            pr.amount_total = sum(line.price_subtotal for line in pr.line_ids)

    def action_request_approval(self):
        self.ensure_one()
        if self.approval_state != 'draft':
            raise UserError("Approval sudah diminta atau PR sudah diproses.")
        flows = self.env['custom.approval.flow'].search([
            ('model_id.model', '=', 'custom.purchase.request'),
            ('min_amount', '<=', self.amount_total)
        ], order='level asc')

        def domain_filter(flow):
            if not flow.condition_domain:
                return True
            domain = safe_eval(flow.condition_domain, {'self': self})
            return self.search_count(domain) > 0

        flows = flows.filtered(domain_filter)

        if not flows:
            self.approval_state = 'approved'
            self.message_post(body="PR tidak memerlukan approval, langsung disetujui.")
            return

        self.env['custom.approval.request'].search([('pr_id', '=', self.id)]).unlink()

        first_level = flows[0]
        approver_group = first_level.approver_group_id
        approvers = self.env['res.users'].search([('groups_id', 'in', approver_group.id)])
        if not approvers:
            raise UserError(f"Tidak ada approver di grup {approver_group.name} untuk level {first_level.level}")

        for user in approvers:
            self.env['custom.approval.request'].create({
                'pr_id': self.id,
                'approval_flow_id': first_level.id,
                'level': first_level.level,
                'approver_id': user.id,
                'state': 'pending',
            })
        self.approval_state = 'pending'
        self.message_post(body="Permintaan approval telah dibuat dan menunggu persetujuan.")

    def _check_approval_progress(self, approved_request):
        self.ensure_one()
        requests_current_level = self.env['custom.approval.request'].search([
            ('pr_id', '=', self.id),
            ('level', '=', approved_request.level),
        ])
        if any(r.state == 'rejected' for r in requests_current_level):
            self.approval_state = 'rejected'
            self.message_post(body="PR ditolak pada level approval.")
            return

        if all(r.state == 'approved' for r in requests_current_level):
            next_level = self.env['custom.approval.flow'].search([
                ('model_id.model', '=', 'custom.purchase.request'),
                ('min_amount', '<=', self.amount_total),
                ('level', '>', approved_request.level)
            ], order='level asc', limit=1)
            if next_level:
                approver_group = next_level.approver_group_id
                approvers = self.env['res.users'].search([('groups_id', 'in', approver_group.id)])
                if not approvers:
                    raise UserError(f"Tidak ada approver di grup {approver_group.name} untuk level {next_level.level}")
                for user in approvers:
                    self.env['custom.approval.request'].create({
                        'pr_id': self.id,
                        'approval_flow_id': next_level.id,
                        'level': next_level.level,
                        'approver_id': user.id,
                        'state': 'pending',
                    })
                self.message_post(body=f"PR lanjut ke level approval {next_level.level}.")
                self.approval_state = 'pending'
            else:
                self.approval_state = 'approved'
                self.message_post(body="PR telah disetujui semua level approval.")

    def action_create_po(self):
        self.ensure_one()
        if self.approval_state != 'approved':
            raise UserError("PR harus disetujui terlebih dahulu sebelum membuat PO.")
        if self.purchase_order_id:
            raise UserError("PO sudah dibuat untuk PR ini.")
        # Buat PO dari PR
        po_vals = {
            'partner_id': self.env.company.partner_id.id,
            'origin': self.name,
            'pr_id': self.id,
            'order_line': [],
        }
        po = self.env['purchase.order'].create(po_vals)
        for line in self.line_ids:
            self.env['purchase.order.line'].create({
                'order_id': po.id,
                'product_id': line.product_id.id,
                'name': line.product_id.display_name,
                'product_qty': line.product_qty,
                'price_unit': line.price_unit,
                'product_uom': line.product_uom.id,
            })
        self.purchase_order_id = po.id
        self.approval_state = 'po_created'
        self.message_post(body=f"PO {po.name} dibuat dari PR ini.")
        return po
