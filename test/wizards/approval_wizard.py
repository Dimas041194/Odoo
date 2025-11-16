# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class ApprovalWizard(models.TransientModel):
    _name = 'approval.wizard'
    _description = 'Approval Action Wizard'

    workflow_id = fields.Many2one('approval.workflow', string='Workflow', required=True)
    action_type = fields.Selection([
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('cancel', 'Cancel'),
    ], string='Action', required=True)
    comments = fields.Text('Comments')

    def action_confirm(self):
        """Confirm the approval action"""
        self.ensure_one()
        
        if self.action_type == 'approve':
            self.workflow_id.action_approve(self.env.user.id, self.comments)
        elif self.action_type == 'reject':
            self.workflow_id.action_reject(self.env.user.id, self.comments)
        elif self.action_type == 'cancel':
            self.workflow_id.action_cancel()
        
        return {'type': 'ir.actions.act_window_close'}


class BulkApprovalWizard(models.TransientModel):
    _name = 'bulk.approval.wizard'
    _description = 'Bulk Approval Wizard'

    workflow_ids = fields.Many2many('approval.workflow', string='Workflows', required=True)
    action_type = fields.Selection([
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('cancel', 'Cancel'),
    ], string='Action', required=True)
    comments = fields.Text('Comments')

    def action_confirm(self):
        """Confirm bulk approval action"""
        self.ensure_one()
        
        for workflow in self.workflow_ids:
            if self.action_type == 'approve':
                workflow.action_approve(self.env.user.id, self.comments)
            elif self.action_type == 'reject':
                workflow.action_reject(self.env.user.id, self.comments)
            elif self.action_type == 'cancel':
                workflow.action_cancel()
        
        return {'type': 'ir.actions.act_window_close'}


class MatrixConfigWizard(models.TransientModel):
    _name = 'matrix.config.wizard'
    _description = 'Matrix Configuration Wizard'

    matrix_id = fields.Many2one('multi.matrix', string='Matrix')
    workflow_type = fields.Selection([
        ('purchase', 'Purchase Order'),
        ('expense', 'Expense Report'),
        ('leave', 'Leave Request'),
        ('travel', 'Travel Request'),
        ('contract', 'Contract Approval'),
        ('custom', 'Custom Workflow')
    ], string='Workflow Type')
    amount = fields.Float('Amount')
    department_id = fields.Many2one('hr.department', string='Department')
    category_id = fields.Many2one('product.category', string='Category')
    suggested_matrix = fields.Char('Suggested Matrix', readonly=True)
    custom_rules = fields.Text('Custom Rules')

    def action_apply(self):
        """Apply matrix configuration"""
        self.ensure_one()
        # Implementation for applying matrix configuration
        return {'type': 'ir.actions.act_window_close'}


class NotificationTestWizard(models.TransientModel):
    _name = 'notification.test.wizard'
    _description = 'Notification Test Wizard'

    template_id = fields.Many2one('notification.template', string='Template', required=True)
    test_email = fields.Char('Test Email', required=True)
    workflow_data = fields.Text('Workflow Data', default='{}')

    def action_send_test(self):
        """Send test notification"""
        self.ensure_one()
        # Implementation for sending test notification
        return {'type': 'ir.actions.act_window_close'}
