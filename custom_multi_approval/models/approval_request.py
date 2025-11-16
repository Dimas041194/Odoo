from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ApprovalRequest(models.Model):
    _name = 'custom.approval.request'
    _inherit = ['mail.thread']
    _description = 'Approval Request'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    model = fields.Char(string='Model', required=True)
    res_id = fields.Integer(string='Record ID', required=True)
    requester_id = fields.Many2one('res.users', string='Requester', default=lambda self: self.env.user)
    approval_line_ids = fields.One2many('custom.approval.line', 'approval_request_id', string='Approval Lines')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='draft', tracking=True)
    current_level = fields.Integer(string='Current Approval Level', default=0)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('custom.approval.request') or 'New'
        return super().create(vals)

    def action_submit(self):
        self.ensure_one()
        if not self.approval_line_ids:
            raise UserError(_('Approval flow not configured.'))
        self.state = 'pending'
        self.current_level = 1
        self._notify_approvers()
        self.message_post(body=_('Approval request submitted.'))

    def _notify_approvers(self):
        current_lines = self.approval_line_ids.filtered(lambda l: l.level == self.current_level and l.state == 'pending')
        for line in current_lines:
            users = line.approver_group_id.users
            for user in users:
                template = self.env.ref('custom_multi_approval.email_template_approval_request')
                template.sudo().with_context(user=user).send_mail(self.id, force_send=True)

    def action_approve(self, comment):
        self.ensure_one()
        user = self.env.user
        line = self.approval_line_ids.filtered(lambda l: l.level == self.current_level and user in l.approver_group_id.users and l.state == 'pending')
        if not line:
            raise UserError(_('You are not authorized to approve at this level or already approved.'))
        line.write({'state': 'approved', 'comment': comment, 'approved_date': fields.Datetime.now()})
        self.message_post(body=_('Approved by %s: %s' % (user.name, comment)))
        lines_current = self.approval_line_ids.filtered(lambda l: l.level == self.current_level)
        approved_count = len(lines_current.filtered(lambda l: l.state == 'approved'))
        if approved_count >= lines_current[0].min_approvers:
            next_level = self.current_level + 1
            if self.approval_line_ids.filtered(lambda l: l.level == next_level):
                self.current_level = next_level
                self._notify_approvers()
            else:
                self.state = 'approved'
                self.message_post(body=_('Approval process completed.'))
                self._post_approval_action()

    def action_reject(self, comment):
        self.ensure_one()
        user = self.env.user
        line = self.approval_line_ids.filtered(lambda l: l.level == self.current_level and user in l.approver_group_id.users and l.state == 'pending')
        if not line:
            raise UserError(_('You are not authorized to reject at this level or already acted.'))
        line.write({'state': 'rejected', 'comment': comment, 'approved_date': fields.Datetime.now()})
        self.state = 'rejected'
        self.message_post(body=_('Rejected by %s: %s' % (user.name, comment)))
        self._post_rejection_action()

    def _post_approval_action(self):
        target_model = self.env[self.model]
        record = target_model.browse(self.res_id)
        # Contoh integrasi: jika purchase.order dan state draft, confirm order
        if self.model == 'purchase.order' and record.state == 'draft':
            record.button_confirm()
        # Tambahkan logika lain sesuai kebutuhan

    def _post_rejection_action(self):
        # Kirim notifikasi ke requester atau rollback
        pass

    @api.model
    def send_reminder(self):
        pending_requests = self.search([('state', '=', 'pending')])
        template = self.env.ref('custom_multi_approval.email_template_approval_reminder')
        for request in pending_requests:
            current_lines = request.approval_line_ids.filtered(lambda l: l.level == request.current_level and l.state == 'pending')
            for line in current_lines:
                users = line.approver_group_id.users
                for user in users:
                    template.sudo().with_context(user=user).send_mail(request.id, force_send=True)
