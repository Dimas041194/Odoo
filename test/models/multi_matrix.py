# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import json


class MultiMatrix(models.Model):
    _name = 'multi.matrix'
    _description = 'Multi Approval Matrix'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char('Matrix Name', required=True, translate=True)
    description = fields.Text('Description', translate=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    
    # Matrix Configuration
    matrix_type = fields.Selection([
        ('amount', 'Amount Based'),
        ('department', 'Department Based'),
        ('category', 'Category Based'),
        ('custom', 'Custom Rules'),
        ('hybrid', 'Hybrid (Multiple Criteria)')
    ], string='Matrix Type', required=True, default='amount')
    
    # Approval Levels
    approval_levels = fields.One2many('multi.matrix.level', 'matrix_id', string='Approval Levels')
    level_count = fields.Integer('Level Count', compute='_compute_level_count', store=True)
    
    # Conditions and Rules
    conditions = fields.Text('Custom Conditions', help='JSON format for custom conditions')
    department_ids = fields.Many2many('hr.department', string='Applicable Departments')
    category_ids = fields.Many2many('product.category', string='Applicable Categories')
    
    # Amount Configuration
    min_amount = fields.Float('Minimum Amount', default=0.0)
    max_amount = fields.Float('Maximum Amount', default=0.0)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Status and Validation
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('archived', 'Archived')
    ], string='Status', default='draft', required=True)
    
    # Statistics
    total_approvals = fields.Integer('Total Approvals', compute='_compute_statistics')
    pending_approvals = fields.Integer('Pending Approvals', compute='_compute_statistics')
    completed_approvals = fields.Integer('Completed Approvals', compute='_compute_statistics')
    
    @api.depends('approval_levels')
    def _compute_level_count(self):
        for record in self:
            record.level_count = len(record.approval_levels)
    
    @api.depends('approval_levels.workflow_ids')
    def _compute_statistics(self):
        for record in self:
            workflows = self.env['approval.workflow'].search([
                ('matrix_id', '=', record.id)
            ])
            record.total_approvals = len(workflows)
            record.pending_approvals = len(workflows.filtered(lambda w: w.state == 'pending'))
            record.completed_approvals = len(workflows.filtered(lambda w: w.state == 'approved'))
    
    @api.constrains('approval_levels')
    def _check_approval_levels(self):
        for record in self:
            if not record.approval_levels:
                raise ValidationError(_('At least one approval level is required.'))
            
            # Check for duplicate levels
            levels = record.approval_levels.mapped('level_sequence')
            if len(levels) != len(set(levels)):
                raise ValidationError(_('Approval levels must have unique sequence numbers.'))
    
    @api.constrains('min_amount', 'max_amount')
    def _check_amount_range(self):
        for record in self:
            if record.matrix_type == 'amount' and record.min_amount > record.max_amount:
                raise ValidationError(_('Minimum amount cannot be greater than maximum amount.'))
    
    def action_activate(self):
        """Activate the matrix"""
        self.write({'state': 'active'})
        return True
    
    def action_archive(self):
        """Archive the matrix"""
        self.write({'state': 'archived'})
        return True
    
    def action_duplicate(self):
        """Duplicate the matrix with all its levels"""
        self.ensure_one()
        new_matrix = self.copy({
            'name': f"{self.name} (Copy)",
            'state': 'draft'
        })
        
        # Copy approval levels
        for level in self.approval_levels:
            level.copy({
                'matrix_id': new_matrix.id
            })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Duplicated Matrix'),
            'res_model': 'multi.matrix',
            'res_id': new_matrix.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def get_applicable_matrix(self, amount=0.0, department_id=None, category_id=None, custom_data=None):
        """Get the applicable matrix based on conditions"""
        domain = [('active', '=', True), ('state', '=', 'active')]
        
        if self.matrix_type == 'amount':
            domain.extend([
                ('min_amount', '<=', amount),
                '|', ('max_amount', '=', 0), ('max_amount', '>=', amount)
            ])
        elif self.matrix_type == 'department' and department_id:
            domain.append(('department_ids', 'in', [department_id]))
        elif self.matrix_type == 'category' and category_id:
            domain.append(('category_ids', 'in', [category_id]))
        elif self.matrix_type == 'custom' and custom_data:
            # Custom logic for custom conditions
            pass
        
        matrices = self.search(domain, order='sequence, min_amount desc')
        return matrices[0] if matrices else False
    
    def validate_approval_conditions(self, workflow_data):
        """Validate if the workflow meets matrix conditions"""
        if self.matrix_type == 'amount':
            amount = workflow_data.get('amount', 0)
            if amount < self.min_amount or (self.max_amount > 0 and amount > self.max_amount):
                return False, _('Amount does not meet matrix criteria.')
        
        if self.matrix_type == 'department':
            department_id = workflow_data.get('department_id')
            if department_id not in self.department_ids.ids:
                return False, _('Department does not match matrix criteria.')
        
        if self.matrix_type == 'category':
            category_id = workflow_data.get('category_id')
            if category_id not in self.category_ids.ids:
                return False, _('Category does not match matrix criteria.')
        
        return True, _('Matrix conditions validated successfully.')


class MultiMatrixLevel(models.Model):
    _name = 'multi.matrix.level'
    _description = 'Approval Level in Multi Matrix'
    _order = 'level_sequence'

    matrix_id = fields.Many2one('multi.matrix', string='Matrix', required=True, ondelete='cascade')
    name = fields.Char('Level Name', required=True)
    level_sequence = fields.Integer('Sequence', required=True, default=1)
    description = fields.Text('Description')
    
    # Approval Configuration
    approval_type = fields.Selection([
        ('single', 'Single Approver'),
        ('multiple', 'Multiple Approvers'),
        ('any', 'Any One Approver'),
        ('all', 'All Approvers'),
        ('percentage', 'Percentage Based'),
        ('quorum', 'Quorum Based')
    ], string='Approval Type', required=True, default='single')
    
    # Approvers
    approver_ids = fields.Many2many('res.users', 'multi_matrix_level_approver_rel', 'level_id', 'user_id', string='Approvers')
    approver_groups = fields.Many2many('res.groups', 'multi_matrix_level_group_rel', 'level_id', 'group_id', string='Approver Groups')
    dynamic_approver_field = fields.Char('Dynamic Approver Field', 
        help='Field name to get dynamic approvers (e.g., department.manager_id)')
    
    # Approval Rules
    required_approvals = fields.Integer('Required Approvals', default=1)
    approval_percentage = fields.Float('Approval Percentage', default=100.0)
    quorum_size = fields.Integer('Quorum Size', default=1)
    
    # Conditions
    condition_amount_min = fields.Float('Minimum Amount for This Level')
    condition_amount_max = fields.Float('Maximum Amount for This Level')
    condition_department_ids = fields.Many2many('hr.department', 'multi_matrix_level_dept_rel', 'level_id', 'dept_id', string='Required Departments')
    condition_category_ids = fields.Many2many('product.category', 'multi_matrix_level_cat_rel', 'level_id', 'cat_id', string='Required Categories')
    
    # Timeout and Escalation
    timeout_hours = fields.Integer('Timeout (Hours)', default=0, help='0 means no timeout')
    escalation_user_ids = fields.Many2many('res.users', 'multi_matrix_level_escalation_rel', 'level_id', 'user_id', string='Escalation Users')
    auto_approve = fields.Boolean('Auto Approve on Timeout', default=False)
    
    # Notifications
    notify_approvers = fields.Boolean('Notify Approvers', default=True)
    notify_requester = fields.Boolean('Notify Requester', default=True)
    notify_escalation = fields.Boolean('Notify on Escalation', default=True)
    
    # Workflow Relations
    workflow_ids = fields.One2many('approval.workflow', 'current_level_id', string='Current Workflows')
    
    @api.constrains('level_sequence')
    def _check_level_sequence(self):
        for record in self:
            if record.level_sequence <= 0:
                raise ValidationError(_('Level sequence must be greater than 0.'))
    
    @api.constrains('required_approvals', 'approver_ids')
    def _check_approval_requirements(self):
        for record in self:
            if record.approval_type in ['multiple', 'all'] and record.required_approvals > len(record.approver_ids):
                raise ValidationError(_('Required approvals cannot exceed number of approvers.'))
    
    def get_available_approvers(self, workflow_data=None):
        """Get list of available approvers for this level"""
        approvers = self.env['res.users']
        
        # Add direct approvers
        if self.approver_ids:
            approvers |= self.approver_ids
        
        # Add group-based approvers
        if self.approver_groups:
            group_users = self.env['res.users'].search([
                ('groups_id', 'in', self.approver_groups.ids)
            ])
            approvers |= group_users
        
        # Add dynamic approvers
        if self.dynamic_approver_field and workflow_data:
            # This would need to be implemented based on specific field requirements
            pass
        
        return approvers.filtered(lambda u: u.active)
    
    def can_approve(self, user_id, workflow_data=None):
        """Check if user can approve at this level"""
        approvers = self.get_available_approvers(workflow_data)
        return user_id in approvers.ids
    
    def get_approval_status(self, workflow_id):
        """Get approval status for this level in a specific workflow"""
        workflow = self.env['approval.workflow'].browse(workflow_id)
        approvals = workflow.approval_ids.filtered(lambda a: a.level_id == self)
        
        if self.approval_type == 'single':
            return 'approved' if approvals.filtered(lambda a: a.state == 'approved') else 'pending'
        elif self.approval_type == 'all':
            return 'approved' if len(approvals.filtered(lambda a: a.state == 'approved')) == len(self.approver_ids) else 'pending'
        elif self.approval_type == 'any':
            return 'approved' if approvals.filtered(lambda a: a.state == 'approved') else 'pending'
        elif self.approval_type == 'multiple':
            approved_count = len(approvals.filtered(lambda a: a.state == 'approved'))
            return 'approved' if approved_count >= self.required_approvals else 'pending'
        
        return 'pending'
