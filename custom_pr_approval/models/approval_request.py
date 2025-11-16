from odoo import models, fields
from odoo.exceptions import UserError

class CustomApprovalRequest(models.Model):
    _name = 'custom.approval.request'
    _description = 'Approval Request'

    pr_id = fields.Many2one('custom.purchase.request', string='Purchase Request', required=True, ondelete='cascade')
    approval_flow_id = fields.Many2one('custom.approval.flow', string='Approval Flow', required=True)
    level = fields.Integer(string='Level', required=True)
    approver_id = fields.Many2one('res.users', string='Approver', required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending', string='Status')
    date_approved = fields.Datetime(string='Date Approved')

    def action_approve(self):
        self.ensure_one()
        if self.state != 'pending':
            raise UserError("Approval request sudah diproses.")
        self.state = 'approved'
        self.date_approved = fields.Datetime.now()
        self.pr_id._check_approval_progress(self)
        self.pr_id.message_post(body=f"PR disetujui oleh {self.approver_id.name} pada level {self.level}")

    def action_reject(self):
        self.ensure_one()
        if self.state != 'pending':
            raise UserError("Approval request sudah diproses.")
        self.state = 'rejected'
        self.date_approved = fields.Datetime.now()
        self.pr_id.approval_state = 'rejected'
        self.pr_id.message_post(body=f"PR ditolak oleh {self.approver_id.name} pada level {self.level}")
