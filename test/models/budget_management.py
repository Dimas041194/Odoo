# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import json
from datetime import datetime, timedelta


class BudgetManagement(models.Model):
    _name = 'budget.management'
    _description = 'Advanced Budget Management System'
    _order = 'fiscal_year desc, name'
    _rec_name = 'name'

    name = fields.Char('Budget Name', required=True)
    code = fields.Char('Budget Code', required=True)
    description = fields.Text('Description')
    
    # Budget Period
    fiscal_year = fields.Many2one('account.fiscal.year', string='Fiscal Year', required=True)
    date_from = fields.Date('Start Date', required=True)
    date_to = fields.Date('End Date', required=True)
    
    # Budget Scope
    department_id = fields.Many2one('hr.department', string='Department')
    project_id = fields.Many2one('project.project', string='Project')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    
    # Budget Amounts
    total_budget = fields.Float('Total Budget Amount', required=True, default=0.0)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Calculated Fields
    committed_amount = fields.Float('Committed Amount', compute='_compute_budget_amounts', store=True)
    actual_amount = fields.Float('Actual Amount', compute='_compute_budget_amounts', store=True)
    available_amount = fields.Float('Available Amount', compute='_compute_budget_amounts', store=True)
    utilization_percentage = fields.Float('Utilization %', compute='_compute_budget_amounts', store=True)
    
    # Budget Lines
    budget_line_ids = fields.One2many('budget.line', 'budget_id', string='Budget Lines')
    commitment_ids = fields.One2many('budget.commitment', 'budget_id', string='Commitments')
    alert_ids = fields.One2many('budget.alert', 'budget_id', string='Alerts')
    
    # Status and Control
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True)
    
    # Approval Integration
    approval_workflow_id = fields.Many2one('approval.workflow', string='Approval Workflow')
    requires_approval = fields.Boolean('Requires Approval', default=True)
    
    # Overbudget Settings
    allow_overbudget = fields.Boolean('Allow Overbudget', default=True)
    overbudget_threshold = fields.Float('Overbudget Threshold %', default=100.0, help='Percentage when overbudget alert is triggered')
    overbudget_approval_required = fields.Boolean('Overbudget Approval Required', default=True)
    
    # Auto Budget Settings
    auto_budget_enabled = fields.Boolean('Auto Budget Enabled', default=True)
    auto_commit_enabled = fields.Boolean('Auto Commit Enabled', default=True)
    auto_alert_enabled = fields.Boolean('Auto Alert Enabled', default=True)
    
    # Notification Settings
    alert_thresholds = fields.Text('Alert Thresholds', default='[{"percentage": 80, "type": "warning"}, {"percentage": 95, "type": "danger"}, {"percentage": 100, "type": "critical"}]')
    notification_recipients = fields.Many2many('res.users', 'budget_management_notification_rel', 'budget_id', 'user_id', string='Notification Recipients')
    
    # Statistics
    total_commitments = fields.Integer('Total Commitments', compute='_compute_statistics')
    total_alerts = fields.Integer('Total Alerts', compute='_compute_statistics')
    overbudget_count = fields.Integer('Overbudget Count', compute='_compute_statistics')
    
    @api.depends('budget_line_ids', 'commitment_ids')
    def _compute_budget_amounts(self):
        for record in self:
            # Calculate committed amount from all commitments
            record.committed_amount = sum(record.commitment_ids.mapped('amount'))
            
            # Calculate actual amount from actual expenses
            record.actual_amount = sum(record.budget_line_ids.mapped('actual_amount'))
            
            # Calculate available amount
            record.available_amount = record.total_budget - record.committed_amount
            
            # Calculate utilization percentage
            if record.total_budget > 0:
                record.utilization_percentage = (record.committed_amount / record.total_budget) * 100
            else:
                record.utilization_percentage = 0.0
    
    @api.depends('commitment_ids', 'alert_ids')
    def _compute_statistics(self):
        for record in self:
            record.total_commitments = len(record.commitment_ids)
            record.total_alerts = len(record.alert_ids)
            record.overbudget_count = len(record.alert_ids.filtered(lambda a: a.alert_type == 'overbudget'))
    
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to and record.date_from > record.date_to:
                raise ValidationError(_('Start date must be before end date.'))
    
    @api.constrains('total_budget')
    def _check_budget_amount(self):
        for record in self:
            if record.total_budget < 0:
                raise ValidationError(_('Budget amount cannot be negative.'))
    
    def action_activate(self):
        """Activate budget"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft budgets can be activated.'))
        
        # Check if approval is required
        if self.requires_approval and not self.approval_workflow_id:
            self._create_approval_workflow()
            return
        
        self.write({'state': 'active'})
        self._setup_auto_budget()
    
    def action_close(self):
        """Close budget"""
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_('Only active budgets can be closed.'))
        
        self.write({'state': 'closed'})
    
    def action_cancel(self):
        """Cancel budget"""
        self.ensure_one()
        if self.state == 'closed':
            raise UserError(_('Closed budgets cannot be cancelled.'))
        
        self.write({'state': 'cancelled'})
    
    def _create_approval_workflow(self):
        """Create approval workflow for budget"""
        self.ensure_one()
        
        workflow = self.env['approval.workflow'].create({
            'name': f'Budget Approval: {self.name}',
            'workflow_type': 'budget',
            'amount': self.total_budget,
            'department_id': self.department_id.id if self.department_id else None,
            'related_model': 'budget.management',
            'related_record_id': self.id,
            'description': f'Budget approval for {self.name} - Amount: {self.total_budget} {self.currency_id.name}',
        })
        
        workflow.action_submit()
        self.approval_workflow_id = workflow.id
    
    def _setup_auto_budget(self):
        """Setup automatic budget monitoring"""
        self.ensure_one()
        
        if self.auto_alert_enabled:
            self._create_alert_thresholds()
        
        # Setup automatic commitment tracking
        if self.auto_commit_enabled:
            self._setup_commitment_tracking()
    
    def _create_alert_thresholds(self):
        """Create alert thresholds based on configuration"""
        self.ensure_one()
        
        try:
            thresholds = json.loads(self.alert_thresholds)
            for threshold in thresholds:
                self.env['budget.alert'].create({
                    'budget_id': self.id,
                    'threshold_percentage': threshold['percentage'],
                    'alert_type': threshold['type'],
                    'is_active': True,
                })
        except (json.JSONDecodeError, KeyError):
            # Create default thresholds
            default_thresholds = [
                {'percentage': 80, 'type': 'warning'},
                {'percentage': 95, 'type': 'danger'},
                {'percentage': 100, 'type': 'critical'},
            ]
            for threshold in default_thresholds:
                self.env['budget.alert'].create({
                    'budget_id': self.id,
                    'threshold_percentage': threshold['percentage'],
                    'alert_type': threshold['type'],
                    'is_active': True,
                })
    
    def _setup_commitment_tracking(self):
        """Setup automatic commitment tracking for all modules"""
        self.ensure_one()
        
        # This will be called when budget is activated
        # The actual tracking is done in the commitment model
        pass
    
    def check_budget_availability(self, amount, module_name, record_id):
        """Check if budget is available for the given amount"""
        self.ensure_one()
        
        if not self.auto_budget_enabled:
            return True, 'Budget checking disabled'
        
        if self.state != 'active':
            return False, 'Budget is not active'
        
        # Check if amount exceeds available budget
        if amount > self.available_amount:
            if not self.allow_overbudget:
                return False, 'Insufficient budget available'
            
            # Check if overbudget approval is required
            if self.overbudget_approval_required:
                return self._handle_overbudget_approval(amount, module_name, record_id)
            else:
                self._create_overbudget_alert(amount, module_name, record_id)
                return True, 'Overbudget allowed with alert'
        
        return True, 'Budget available'
    
    def _handle_overbudget_approval(self, amount, module_name, record_id):
        """Handle overbudget approval process"""
        self.ensure_one()
        
        # Create overbudget approval workflow
        workflow = self.env['approval.workflow'].create({
            'name': f'Overbudget Approval: {self.name}',
            'workflow_type': 'overbudget',
            'amount': amount,
            'department_id': self.department_id.id if self.department_id else None,
            'related_model': module_name,
            'related_record_id': record_id,
            'description': f'Overbudget approval for {module_name} - Amount: {amount} {self.currency_id.name}',
        })
        
        workflow.action_submit()
        
        # Create overbudget alert
        self._create_overbudget_alert(amount, module_name, record_id)
        
        return False, 'Overbudget approval required'
    
    def _create_overbudget_alert(self, amount, module_name, record_id):
        """Create overbudget alert"""
        self.ensure_one()
        
        alert = self.env['budget.alert'].create({
            'budget_id': self.id,
            'alert_type': 'overbudget',
            'threshold_percentage': (self.committed_amount + amount) / self.total_budget * 100,
            'amount': amount,
            'module_name': module_name,
            'record_id': record_id,
            'message': f'Overbudget detected: {amount} {self.currency_id.name} for {module_name}',
            'is_active': True,
        })
        
        # Send notifications
        self._send_overbudget_notifications(alert)
        
        return alert
    
    def _send_overbudget_notifications(self, alert):
        """Send overbudget notifications"""
        self.ensure_one()
        
        # Get notification recipients
        recipients = self.notification_recipients or self.department_id.member_ids.mapped('user_id')
        
        if not recipients:
            return
        
        # Create notification template
        template = self.env['notification.template'].search([
            ('template_type', '=', 'overbudget_alert'),
            ('active', '=', True)
        ], limit=1)
        
        if not template:
            # Create default template
            template = self.env['notification.template'].create({
                'name': 'Overbudget Alert',
                'template_type': 'overbudget_alert',
                'recipient_type': 'custom',
                'subject': 'Overbudget Alert: {{budget.name}}',
                'body_html': '''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #dc3545;">Overbudget Alert</h2>
                        <p>Dear {{recipient.name}},</p>
                        <p>An overbudget situation has been detected in the budget system.</p>
                        
                        <div style="background-color: #f8d7da; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #dc3545;">
                            <h3 style="margin-top: 0; color: #721c24;">Budget Details</h3>
                            <p><strong>Budget:</strong> {{budget.name}}</p>
                            <p><strong>Department:</strong> {{budget.department}}</p>
                            <p><strong>Total Budget:</strong> {{budget.total_budget}} {{budget.currency}}</p>
                            <p><strong>Committed Amount:</strong> {{budget.committed_amount}} {{budget.currency}}</p>
                            <p><strong>Available Amount:</strong> {{budget.available_amount}} {{budget.currency}}</p>
                            <p><strong>Overbudget Amount:</strong> {{alert.amount}} {{budget.currency}}</p>
                            <p><strong>Module:</strong> {{alert.module_name}}</p>
                        </div>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="/web#id={{budget.id}}&model=budget.management&view_type=form" 
                               style="background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                                View Budget
                            </a>
                        </div>
                    </div>
                ''',
                'active': True,
            })
        
        # Send notifications
        for recipient in recipients:
            self.env['email.service'].send_notification_email(
                template_id=template.id,
                recipient_data={
                    'type': 'email',
                    'email': recipient.email,
                    'user_id': recipient.id,
                },
                workflow_data={
                    'budget': {
                        'id': self.id,
                        'name': self.name,
                        'department': self.department_id.name if self.department_id else '',
                        'total_budget': self.total_budget,
                        'committed_amount': self.committed_amount,
                        'available_amount': self.available_amount,
                        'currency': self.currency_id.name,
                    },
                    'alert': {
                        'amount': alert.amount,
                        'module_name': alert.module_name,
                    }
                }
            )
    
    def create_commitment(self, amount, module_name, record_id, description=''):
        """Create budget commitment"""
        self.ensure_one()
        
        commitment = self.env['budget.commitment'].create({
            'budget_id': self.id,
            'amount': amount,
            'module_name': module_name,
            'record_id': record_id,
            'description': description,
            'commitment_date': fields.Date.today(),
        })
        
        # Check if this creates an overbudget situation
        if self.committed_amount > self.total_budget:
            self._create_overbudget_alert(amount, module_name, record_id)
        
        return commitment
    
    def release_commitment(self, module_name, record_id):
        """Release budget commitment"""
        self.ensure_one()
        
        commitments = self.env['budget.commitment'].search([
            ('budget_id', '=', self.id),
            ('module_name', '=', module_name),
            ('record_id', '=', record_id),
            ('state', '=', 'active')
        ])
        
        for commitment in commitments:
            commitment.action_release()
    
    def get_budget_status(self):
        """Get current budget status"""
        self.ensure_one()
        
        return {
            'budget_id': self.id,
            'name': self.name,
            'total_budget': self.total_budget,
            'committed_amount': self.committed_amount,
            'actual_amount': self.actual_amount,
            'available_amount': self.available_amount,
            'utilization_percentage': self.utilization_percentage,
            'state': self.state,
            'is_overbudget': self.committed_amount > self.total_budget,
            'overbudget_amount': max(0, self.committed_amount - self.total_budget),
        }
    
    @api.model
    def get_available_budget(self, department_id=None, project_id=None, analytic_account_id=None):
        """Get available budget for given criteria"""
        domain = [
            ('state', '=', 'active'),
            ('auto_budget_enabled', '=', True),
            ('date_from', '<=', fields.Date.today()),
            ('date_to', '>=', fields.Date.today()),
        ]
        
        if department_id:
            domain.append(('department_id', '=', department_id))
        if project_id:
            domain.append(('project_id', '=', project_id))
        if analytic_account_id:
            domain.append(('analytic_account_id', '=', analytic_account_id))
        
        budgets = self.search(domain)
        
        if not budgets:
            return None
        
        # Return the most specific budget (with most criteria matched)
        return budgets[0]
    
    def action_view_commitments(self):
        """View budget commitments"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Budget Commitments'),
            'res_model': 'budget.commitment',
            'view_mode': 'tree,form',
            'domain': [('budget_id', '=', self.id)],
            'context': {'default_budget_id': self.id},
        }
    
    def action_view_alerts(self):
        """View budget alerts"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Budget Alerts'),
            'res_model': 'budget.alert',
            'view_mode': 'tree,form',
            'domain': [('budget_id', '=', self.id)],
            'context': {'default_budget_id': self.id},
        }
