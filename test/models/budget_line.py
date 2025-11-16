# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class BudgetLine(models.Model):
    _name = 'budget.line'
    _description = 'Budget Line Item'
    _order = 'account_id, name'

    budget_id = fields.Many2one('budget.management', string='Budget', required=True, ondelete='cascade')
    name = fields.Char('Description', required=True)
    account_id = fields.Many2one('account.account', string='Account', required=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    
    # Budget Amounts
    planned_amount = fields.Float('Planned Amount', required=True, default=0.0)
    currency_id = fields.Many2one('res.currency', related='budget_id.currency_id', string='Currency', store=True)
    
    # Actual Amounts (computed from commitments and actual expenses)
    committed_amount = fields.Float('Committed Amount', compute='_compute_actual_amounts', store=True)
    actual_amount = fields.Float('Actual Amount', compute='_compute_actual_amounts', store=True)
    available_amount = fields.Float('Available Amount', compute='_compute_actual_amounts', store=True)
    
    # Variance Analysis
    variance_amount = fields.Float('Variance Amount', compute='_compute_variance', store=True)
    variance_percentage = fields.Float('Variance %', compute='_compute_variance', store=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed')
    ], string='Status', default='draft')
    
    # Related Commitments
    commitment_ids = fields.One2many('budget.commitment', 'budget_line_id', string='Commitments')
    
    @api.depends('commitment_ids', 'commitment_ids.amount', 'commitment_ids.state')
    def _compute_actual_amounts(self):
        for record in self:
            # Calculate committed amount from active commitments
            active_commitments = record.commitment_ids.filtered(lambda c: c.state == 'active')
            record.committed_amount = sum(active_commitments.mapped('amount'))
            
            # Calculate actual amount from confirmed commitments
            confirmed_commitments = record.commitment_ids.filtered(lambda c: c.state == 'confirmed')
            record.actual_amount = sum(confirmed_commitments.mapped('amount'))
            
            # Calculate available amount
            record.available_amount = record.planned_amount - record.committed_amount
    
    @api.depends('planned_amount', 'actual_amount')
    def _compute_variance(self):
        for record in self:
            record.variance_amount = record.actual_amount - record.planned_amount
            if record.planned_amount > 0:
                record.variance_percentage = (record.variance_amount / record.planned_amount) * 100
            else:
                record.variance_percentage = 0.0
    
    @api.constrains('planned_amount')
    def _check_planned_amount(self):
        for record in self:
            if record.planned_amount < 0:
                raise ValidationError(_('Planned amount cannot be negative.'))
    
    def action_activate(self):
        """Activate budget line"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft budget lines can be activated.'))
        
        self.write({'state': 'active'})
    
    def action_close(self):
        """Close budget line"""
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_('Only active budget lines can be closed.'))
        
        self.write({'state': 'closed'})
    
    def create_commitment(self, amount, module_name, record_id, description=''):
        """Create commitment for this budget line"""
        self.ensure_one()
        
        if self.state != 'active':
            raise UserError(_('Cannot create commitment for inactive budget line.'))
        
        if amount > self.available_amount:
            raise UserError(_('Insufficient budget available in this line.'))
        
        commitment = self.env['budget.commitment'].create({
            'budget_id': self.budget_id.id,
            'budget_line_id': self.id,
            'amount': amount,
            'module_name': module_name,
            'record_id': record_id,
            'description': description,
            'commitment_date': fields.Date.today(),
        })
        
        return commitment
    
    def get_budget_status(self):
        """Get budget line status"""
        self.ensure_one()
        
        return {
            'budget_line_id': self.id,
            'name': self.name,
            'account_id': self.account_id.name,
            'planned_amount': self.planned_amount,
            'committed_amount': self.committed_amount,
            'actual_amount': self.actual_amount,
            'available_amount': self.available_amount,
            'variance_amount': self.variance_amount,
            'variance_percentage': self.variance_percentage,
            'state': self.state,
            'is_overbudget': self.committed_amount > self.planned_amount,
        }


class BudgetCommitment(models.Model):
    _name = 'budget.commitment'
    _description = 'Budget Commitment Tracking'
    _order = 'commitment_date desc'

    budget_id = fields.Many2one('budget.management', string='Budget', required=True, ondelete='cascade')
    budget_line_id = fields.Many2one('budget.line', string='Budget Line', ondelete='cascade')
    
    # Commitment Details
    amount = fields.Float('Amount', required=True)
    currency_id = fields.Many2one('res.currency', related='budget_id.currency_id', string='Currency', store=True)
    description = fields.Text('Description')
    commitment_date = fields.Date('Commitment Date', required=True, default=fields.Date.today)
    
    # Source Information
    module_name = fields.Char('Source Module', required=True)
    record_id = fields.Integer('Source Record ID', required=True)
    record_name = fields.Char('Source Record Name', compute='_compute_record_name', store=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('released', 'Released')
    ], string='Status', default='draft', required=True)
    
    # Dates
    confirmed_date = fields.Date('Confirmed Date')
    cancelled_date = fields.Date('Cancelled Date')
    released_date = fields.Date('Released Date')
    
    # Approval Integration
    approval_workflow_id = fields.Many2one('approval.workflow', string='Approval Workflow')
    
    @api.depends('module_name', 'record_id')
    def _compute_record_name(self):
        for record in self:
            if record.module_name and record.record_id:
                try:
                    model = self.env[record.module_name]
                    source_record = model.browse(record.record_id)
                    if source_record.exists():
                        record.record_name = source_record.display_name
                    else:
                        record.record_name = f"{record.module_name} #{record.record_id}"
                except:
                    record.record_name = f"{record.module_name} #{record.record_id}"
            else:
                record.record_name = ''
    
    @api.constrains('amount')
    def _check_amount(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_('Commitment amount must be positive.'))
    
    def action_confirm(self):
        """Confirm commitment"""
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_('Only active commitments can be confirmed.'))
        
        self.write({
            'state': 'confirmed',
            'confirmed_date': fields.Date.today()
        })
    
    def action_cancel(self):
        """Cancel commitment"""
        self.ensure_one()
        if self.state not in ['draft', 'active']:
            raise UserError(_('Cannot cancel commitment in current state.'))
        
        self.write({
            'state': 'cancelled',
            'cancelled_date': fields.Date.today()
        })
    
    def action_release(self):
        """Release commitment"""
        self.ensure_one()
        if self.state not in ['active', 'confirmed']:
            raise UserError(_('Cannot release commitment in current state.'))
        
        self.write({
            'state': 'released',
            'released_date': fields.Date.today()
        })
    
    def action_activate(self):
        """Activate commitment"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft commitments can be activated.'))
        
        # Check if budget allows this commitment
        if self.budget_line_id and self.amount > self.budget_line_id.available_amount:
            raise UserError(_('Insufficient budget available in the selected budget line.'))
        
        self.write({'state': 'active'})
    
    @api.model
    def create_commitment(self, budget_id, amount, module_name, record_id, description='', budget_line_id=None):
        """Create budget commitment"""
        commitment = self.create({
            'budget_id': budget_id,
            'budget_line_id': budget_line_id,
            'amount': amount,
            'module_name': module_name,
            'record_id': record_id,
            'description': description,
            'commitment_date': fields.Date.today(),
        })
        
        # Auto-activate if budget allows
        if commitment.budget_id.auto_commit_enabled:
            try:
                commitment.action_activate()
            except UserError:
                # If auto-activation fails, keep as draft for manual review
                pass
        
        return commitment
    
    def get_commitment_status(self):
        """Get commitment status"""
        self.ensure_one()
        
        return {
            'commitment_id': self.id,
            'amount': self.amount,
            'currency': self.currency_id.name,
            'description': self.description,
            'module_name': self.module_name,
            'record_name': self.record_name,
            'state': self.state,
            'commitment_date': self.commitment_date,
            'confirmed_date': self.confirmed_date,
        }


class BudgetAlert(models.Model):
    _name = 'budget.alert'
    _description = 'Budget Alert System'
    _order = 'alert_date desc'

    budget_id = fields.Many2one('budget.management', string='Budget', required=True, ondelete='cascade')
    budget_line_id = fields.Many2one('budget.line', string='Budget Line', ondelete='cascade')
    
    # Alert Details
    alert_type = fields.Selection([
        ('warning', 'Warning'),
        ('danger', 'Danger'),
        ('critical', 'Critical'),
        ('overbudget', 'Overbudget'),
        ('threshold', 'Threshold Reached')
    ], string='Alert Type', required=True)
    
    threshold_percentage = fields.Float('Threshold Percentage')
    amount = fields.Float('Amount')
    currency_id = fields.Many2one('res.currency', related='budget_id.currency_id', string='Currency', store=True)
    
    # Alert Information
    message = fields.Text('Alert Message', required=True)
    alert_date = fields.Datetime('Alert Date', default=fields.Datetime.now)
    
    # Source Information
    module_name = fields.Char('Source Module')
    record_id = fields.Integer('Source Record ID')
    record_name = fields.Char('Source Record Name', compute='_compute_record_name', store=True)
    
    # Status
    state = fields.Selection([
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed')
    ], string='Status', default='active')
    
    # Resolution
    acknowledged_by = fields.Many2one('res.users', string='Acknowledged By')
    acknowledged_date = fields.Datetime('Acknowledged Date')
    resolution_notes = fields.Text('Resolution Notes')
    
    # Notification
    is_active = fields.Boolean('Is Active', default=True)
    notification_sent = fields.Boolean('Notification Sent', default=False)
    
    @api.depends('module_name', 'record_id')
    def _compute_record_name(self):
        for record in self:
            if record.module_name and record.record_id:
                try:
                    model = self.env[record.module_name]
                    source_record = model.browse(record.record_id)
                    if source_record.exists():
                        record.record_name = source_record.display_name
                    else:
                        record.record_name = f"{record.module_name} #{record.record_id}"
                except:
                    record.record_name = f"{record.module_name} #{record.record_id}"
            else:
                record.record_name = ''
    
    def action_acknowledge(self):
        """Acknowledge alert"""
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_('Only active alerts can be acknowledged.'))
        
        self.write({
            'state': 'acknowledged',
            'acknowledged_by': self.env.user.id,
            'acknowledged_date': fields.Datetime.now()
        })
    
    def action_resolve(self):
        """Resolve alert"""
        self.ensure_one()
        if self.state not in ['active', 'acknowledged']:
            raise UserError(_('Only active or acknowledged alerts can be resolved.'))
        
        self.write({
            'state': 'resolved',
            'is_active': False
        })
    
    def action_dismiss(self):
        """Dismiss alert"""
        self.ensure_one()
        if self.state not in ['active', 'acknowledged']:
            raise UserError(_('Only active or acknowledged alerts can be dismissed.'))
        
        self.write({
            'state': 'dismissed',
            'is_active': False
        })
    
    def get_alert_status(self):
        """Get alert status"""
        self.ensure_one()
        
        return {
            'alert_id': self.id,
            'alert_type': self.alert_type,
            'message': self.message,
            'amount': self.amount,
            'currency': self.currency_id.name,
            'threshold_percentage': self.threshold_percentage,
            'state': self.state,
            'alert_date': self.alert_date,
            'module_name': self.module_name,
            'record_name': self.record_name,
        }
