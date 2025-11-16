from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ApprovalRule(models.Model):
    _name = 'pr.approval.rule'
    _description = 'Purchase Request Approval Rule'
    _order = 'sequence'

    name = fields.Char(required=True)
    min_amount = fields.Float(required=True)
    max_amount = fields.Float()
    approver_group_id = fields.Many2one('res.groups', string='Approver Group', required=True)
    sequence = fields.Integer(default=10)
    approval_line_ids = fields.One2many('pr.approval.line', 'rule_id', string='Approval Lines')
    email_template_id = fields.Many2one('mail.template', string='Approval Email Template')

    @api.constrains('min_amount', 'max_amount')
    def _check_amounts(self):
        for rec in self:
            if rec.max_amount and rec.min_amount > rec.max_amount:
                raise UserError(_('Minimum Amount must be less than or equal to Maximum Amount.'))

    def is_last_level(self):
        max_seq = self.search([], order='sequence desc', limit=1).sequence
        return self.sequence == max_seq


class ApprovalLine(models.Model):
    _name = 'pr.approval.line'
    _description = 'Purchase Request Approval Line'

    rule_id = fields.Many2one('pr.approval.rule', ondelete='cascade', required=True)
    user_id = fields.Many2one('res.users', required=True)
    sequence = fields.Integer(default=10)


class ApprovalStatus(models.Model):
    _name = 'pr.approval.status'
    _description = 'Purchase Request Approval Status'

    request_id = fields.Many2one('pr.purchase.request', string='Purchase Request', ondelete='cascade', required=True)
    user_id = fields.Many2one('res.users', string='Approver', required=True)
    status = fields.Selection([('waiting', 'Waiting'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='waiting')
    date = fields.Datetime(string='Date', default=fields.Datetime.now)
    sequence = fields.Integer(string='Sequence', default=10)


class PurchaseRequest(models.Model):
    _name = 'pr.purchase.request'
    _description = 'Purchase Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Request Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    requester_id = fields.Many2one('res.users', string='Requester', default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', string='Vendor (Supplier)', domain="[('supplier_rank','>',0)]")
    date_request = fields.Datetime(string='Request Date', default=fields.Datetime.now)
    line_ids = fields.One2many('pr.purchase.request.line', 'request_id', string='Request Lines')
    total_amount = fields.Monetary(string='Total Amount', compute='_compute_total_amount', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting_approval', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('po_created', 'Purchase Order Created')
    ], default='draft', string='Status', tracking=True)
    approval_level = fields.Integer(string='Approval Level', default=0, readonly=True)
    current_approval_rule_id = fields.Many2one('pr.approval.rule', string='Current Approval Rule', readonly=True)
    approval_status_ids = fields.One2many('pr.approval.status', 'request_id', string='Approval Statuses')
    po_id = fields.Many2one('purchase.order', string='Purchase Order')

    next_approval_user_id = fields.Many2one('res.users', string='Next Approver', compute='_compute_next_approver', store=True)

    @api.depends('approval_status_ids.status', 'approval_status_ids.user_id')
    def _compute_next_approver(self):
        for rec in self:
            waiting_approval = rec.approval_status_ids.filtered(lambda r: r.status == 'waiting')
            waiting_sorted = waiting_approval.sorted('sequence')
            rec.next_approval_user_id = waiting_sorted[0].user_id if waiting_sorted else False

    @api.depends('approval_status_ids.status', 'approval_status_ids.user_id')
    def _compute_user_is_approver(self):
        for rec in self:
            rec.user_is_approver = any(
                status.user_id == self.env.user and status.status == 'waiting' for status in rec.approval_status_ids
            )

    user_is_approver = fields.Boolean(string='User is Approver', compute='_compute_user_is_approver')

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq = self.env['ir.sequence'].next_by_code('pr.purchase.request') or _('New')
            vals['name'] = seq
        return super().create(vals)

    @api.depends('line_ids.price_unit', 'line_ids.product_qty')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(line.price_unit * line.product_qty for line in rec.line_ids)

    def _assign_approval_activity(self, rule):
        self._clear_approval_activity()
        for line in rule.approval_line_ids:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=line.user_id.id,
                summary=_('Please approve Purchase Request %s') % self.name,
                note=_('Purchase Request %s requires your approval at level %s' % (self.name, rule.name)),
            )

    def _clear_approval_activity(self):
        todo_activity = self.env.ref('mail.mail_activity_data_todo')
        activities = self.activity_ids.filtered(lambda r: r.activity_type_id == todo_activity)
        activities.unlink()

    def action_submit(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('Please add at least one product line.'))
            rule = self.env['pr.approval.rule'].search([
                ('min_amount', '<=', rec.total_amount),
                '|', ('max_amount', '>=', rec.total_amount), ('max_amount', '=', False)
            ], order='sequence', limit=1)
            if not rule:
                raise UserError(_('No approval rule found for this amount.'))

            rec.approval_status_ids.unlink()
            sequence = 1
            for line in rule.approval_line_ids.sorted('sequence'):
                self.env['pr.approval.status'].create({
                    'request_id': rec.id,
                    'user_id': line.user_id.id,
                    'status': 'waiting',
                    'sequence': sequence,
                })
                sequence += 1

            rec.state = 'waiting_approval'
            rec.approval_level = rule.sequence
            rec.current_approval_rule_id = rule
            rec._send_approval_email(rule)
            rec._assign_approval_activity(rule)
            rec.message_post(body=_('Submitted for approval level %s.') % rule.name)

    def _send_approval_email(self, rule):
        if rule.email_template_id:
            approvers = self.env['res.users'].search([('groups_id', 'in', rule.approver_group_id.id)])
            emails = approvers.mapped('email')
            if emails:
                rule.email_template_id.with_context(email_to=', '.join(emails)).send_mail(self.id, force_send=True)

    def action_approve(self):
        for rec in self:
            if rec.state != 'waiting_approval':
                raise UserError(_('Purchase Request must be waiting for approval to approve.'))
            current_rule = rec.current_approval_rule_id
            if not current_rule:
                raise UserError(_('Approval rule not set.'))
            if current_rule.approver_group_id not in self.env.user.groups_id:
                raise UserError(_('You are not authorized to approve this level.'))

            rec._clear_approval_activity()

            ap_status = rec.approval_status_ids.filtered(lambda r: r.user_id == self.env.user and r.status == 'waiting')
            if ap_status:
                ap_status.write({'status': 'approved', 'date': fields.Datetime.now()})
            else:
                raise UserError(_('You are not in approval line or already approved.'))

            all_approved = all(status.status == 'approved' for status in rec.approval_status_ids)
            if all_approved:
                rec.state = 'approved'
                rec.message_post(body=_('Approved at level %s.') % current_rule.name)
            else:
                rec.message_post(body=_('Approved by %s, waiting for others.') % self.env.user.name)

    def action_reject(self):
        for rec in self:
            rec._clear_approval_activity()
            rec.state = 'rejected'
            rec.approval_level = 0
            rec.current_approval_rule_id = False
            rec.approval_status_ids.write({'status': 'rejected', 'date': fields.Datetime.now()})
            rec.message_post(body=_('Rejected'))

    def action_reset_draft(self):
        for rec in self:
            rec._clear_approval_activity()
            rec.state = 'draft'
            rec.approval_level = 0
            rec.current_approval_rule_id = False
            rec.approval_status_ids.write({'status': 'waiting', 'date': False})
            rec.message_post(body=_('Reset to Draft'))

    def action_create_po(self):
        po_obj = self.env['purchase.order']
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Purchase Request must be approved before creating Purchase Order.'))
            if not rec.partner_id:
                raise UserError(_('Vendor (Supplier) must be set before creating Purchase Order.'))
            values = {
                'origin': rec.name,
                'partner_id': rec.partner_id.id,
                'order_line': [(0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.product_id.display_name,
                    'product_qty': line.product_qty,
                    'product_uom': line.product_uom.id,
                    'price_unit': line.price_unit,
                }) for line in rec.line_ids]
            }
            po = po_obj.create(values)
            rec.state = 'po_created'
            rec.po_id = po.id
            rec.message_post(body=_('Purchase Order %s created from Purchase Request.') % po.name)
            rec._send_po_created_email()

    def _send_po_created_email(self):
        template = self.env.ref('purchase_request_approval.email_template_po_created', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)


class PurchaseRequestLine(models.Model):
    _name = 'pr.purchase.request.line'
    _description = 'Purchase Request Line'

    request_id = fields.Many2one('pr.purchase.request', string='Purchase Request', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_qty = fields.Float(string='Quantity', default=1.0)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure')
    price_unit = fields.Float(string='Unit Price', default=0.0)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom = self.product_id.uom_id
