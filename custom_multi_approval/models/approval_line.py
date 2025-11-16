from odoo import models, fields

class ApprovalLine(models.Model):
    _name = 'custom.approval.line'
    _description = 'Approval Line'

    approval_request_id = fields.Many2one('custom.approval.request', string='Approval Request', required=True, ondelete='cascade')
    level = fields.Integer(string='Approval Level', required=True)
    approver_group_id = fields.Many2one('res.groups', string='Approver Group', required=True)
    state = fields.Selection([('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending')
    comment = fields.Text(string='Comment')
    approved_date = fields.Datetime(string='Approved Date')
    min_approvers = fields.Integer(string='Minimum Approvers', default=1)
