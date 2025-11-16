from odoo import models, fields

class CustomApprovalFlow(models.Model):
    _name = 'custom.approval.flow'
    _description = 'Approval Flow Configuration'

    name = fields.Char(string='Name', required=True)
    model_id = fields.Many2one('ir.model', string='Target Model', required=True)
    level = fields.Integer(required=True)
    approver_group_id = fields.Many2one('res.groups', string='Approver Group', required=True)
    min_amount = fields.Float(string='Minimum Amount', default=0.0)
    condition_domain = fields.Char(string='Condition Domain')
