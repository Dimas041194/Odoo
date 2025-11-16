from odoo import models, api

class ApprovalMixin(models.AbstractModel):
    _name = 'custom.approval.mixin'
    _description = 'Mixin for automatic approval request'

    @api.model
    def create(self, vals):
        record = super().create(vals)
        self._create_approval_request_if_needed(record)
        return record

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._create_approval_request_if_needed(rec)
        return res

    def _create_approval_request_if_needed(self, record):
        ApprovalFlow = self.env['custom.approval.flow']
        ApprovalRequest = self.env['custom.approval.request']

        model_name = record._name
        flows = ApprovalFlow.search([('model_id.model', '=', model_name)], order='level asc')

        # Filter flows by condition_domain if set
        valid_flows = flows.filtered(lambda f: not f.condition_domain or record.domain_eval(f.condition_domain))

        if not valid_flows:
            return

        # Cek apakah sudah ada approval request pending untuk record ini
        existing = ApprovalRequest.search([('model', '=', model_name), ('res_id', '=', record.id), ('state', 'in', ['pending', 'draft'])])
        if existing:
            return

        # Buat approval request
        approval_request = ApprovalRequest.create({
            'model': model_name,
            'res_id': record.id,
            'requester_id': record.env.user.id,
        })

        # Buat approval lines
        lines_vals = []
        for flow in valid_flows:
            lines_vals.append({
                'level': flow.level,
                'approver_group_id': flow.approver_group_id.id,
                'state': 'pending',
                'min_approvers': flow.min_approvers,
            })
        approval_request.approval_line_ids = [(0, 0, vals) for vals in lines_vals]

        approval_request.action_submit()
