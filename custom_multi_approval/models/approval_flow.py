from odoo import models, fields, api

class ApprovalFlow(models.Model):
    _name = 'custom.approval.flow'
    _description = 'Approval Flow Configuration'
    _order = 'model_id, level'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    model_id = fields.Many2one(
        'ir.model',
        string='Target Model',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(default=10)
    level = fields.Integer(string='Approval Level', required=True)
    approver_group_id = fields.Many2one('res.groups', string='Approver Group', required=True)
    min_approvers = fields.Integer(string='Minimum Approvers', default=1)
    parallel_approval = fields.Boolean(string='Parallel Approval', default=False)
    condition_domain = fields.Char(
        string='Condition Domain',
        help="Domain to filter records for this approval flow, e.g. [('amount_total', '>=', 10000000)]"
    )

    @api.depends('model_id', 'level')
    def _compute_name(self):
        for rec in self:
            model_name = rec.model_id.model or 'Unknown Model'
            rec.name = f"{model_name} - Level {rec.level}"
