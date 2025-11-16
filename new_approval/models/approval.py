from odoo import models, fields, api, _
from odoo.exceptions import UserError
import uuid


class ApprovalRequest(models.Model):
    _name = 'x.new.approval.request'
    _description = 'New Approval Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Request Reference', required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))
    model_name = fields.Char(string='Model Name', required=True)
    record_id = fields.Integer(string='Record ID', required=True)
    current_level = fields.Integer(string='Current Approval Level', default=1)
    max_level = fields.Integer(string='Max Approval Level', required=True)
    approver_ids = fields.Many2many('res.users', string='Approvers')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled')
    ], default='pending', tracking=True)
    token = fields.Char(string='Approval Token', index=True)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('new.approval.request') or _('New')
        vals['token'] = str(uuid.uuid4())
        return super().create(vals)

    def action_approve(self, token=None):
        self.ensure_one()
        if token and token != self.token:
            raise UserError(_('Invalid token.'))
        if self.status != 'pending':
            raise UserError(_('This request has been already processed.'))
        if self.current_level >= self.max_level:
            self.status = 'approved'
            self._update_original_record('approved')
        else:
            self.current_level += 1
            self._send_approval_email()
        return True

    def action_reject(self, token=None):
        self.ensure_one()
        if token and token != self.token:
            raise UserError(_('Invalid token.'))
        if self.status != 'pending':
            raise UserError(_('This request has been already processed.'))
        self.status = 'rejected'
        self._update_original_record('rejected')
        return True

    def _update_original_record(self, result):
        model = self.env[self.model_name]
        record = model.browse(self.record_id)
        if record.exists():
            record.write({'approval_status': result})

    def _send_approval_email(self):
        template = self.env.ref('new_approval.email_template_approval')
        for approver in self.approver_ids:
            template.with_context(
                approval_id=self.id,
                user_id=approver.id,
                token=self.token,
                base_url=self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            ).send_mail(self.id, force_send=True)
