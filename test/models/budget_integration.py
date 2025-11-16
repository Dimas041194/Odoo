# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class BudgetIntegrationMixin(models.AbstractModel):
    _name = 'budget.integration.mixin'
    _description = 'Budget Integration Mixin'

    # Budget Integration Fields
    budget_id = fields.Many2one('budget.management', string='Budget', compute='_compute_budget_id', store=True)
    budget_commitment_id = fields.Many2one('budget.commitment', string='Budget Commitment')
    budget_available = fields.Boolean('Budget Available', compute='_compute_budget_available')
    budget_status = fields.Text('Budget Status', compute='_compute_budget_status')
    
    # Overbudget Fields
    is_overbudget = fields.Boolean('Is Overbudget', compute='_compute_budget_available')
    overbudget_approval_id = fields.Many2one('approval.workflow', string='Overbudget Approval')
    overbudget_allowed = fields.Boolean('Overbudget Allowed', default=False)
    
    @api.depends('department_id', 'analytic_account_id', 'project_id')
    def _compute_budget_id(self):
        for record in self:
            budget = self.env['budget.management'].get_available_budget(
                department_id=record.department_id.id if hasattr(record, 'department_id') else None,
                project_id=record.project_id.id if hasattr(record, 'project_id') else None,
                analytic_account_id=record.analytic_account_id.id if hasattr(record, 'analytic_account_id') else None
            )
            record.budget_id = budget.id if budget else False
    
    @api.depends('budget_id', 'amount_total')
    def _compute_budget_available(self):
        for record in self:
            if not record.budget_id:
                record.budget_available = False
                record.is_overbudget = False
                continue
            
            amount = getattr(record, 'amount_total', 0) or getattr(record, 'amount', 0) or 0
            is_available, message = record.budget_id.check_budget_availability(
                amount, record._name, record.id
            )
            
            record.budget_available = is_available
            record.is_overbudget = not is_available and 'overbudget' in message.lower()
    
    @api.depends('budget_id')
    def _compute_budget_status(self):
        for record in self:
            if record.budget_id:
                status = record.budget_id.get_budget_status()
                record.budget_status = f"Budget: {status['name']} | Available: {status['available_amount']} {status['currency']} | Utilization: {status['utilization_percentage']:.1f}%"
            else:
                record.budget_status = "No budget assigned"
    
    def action_check_budget(self):
        """Check budget availability"""
        self.ensure_one()
        
        if not self.budget_id:
            raise UserError(_('No budget assigned to this record.'))
        
        amount = getattr(self, 'amount_total', 0) or getattr(self, 'amount', 0) or 0
        is_available, message = self.budget_id.check_budget_availability(
            amount, self._name, self.id
        )
        
        if not is_available:
            if 'approval' in message.lower():
                # Create overbudget approval
                self._create_overbudget_approval(amount)
                raise UserError(_('Overbudget approval required. Please wait for approval.'))
            else:
                raise UserError(_(message))
        
        return True
    
    def action_create_budget_commitment(self):
        """Create budget commitment"""
        self.ensure_one()
        
        if not self.budget_id:
            raise UserError(_('No budget assigned to this record.'))
        
        amount = getattr(self, 'amount_total', 0) or getattr(self, 'amount', 0) or 0
        if amount <= 0:
            raise UserError(_('Amount must be greater than zero.'))
        
        # Create commitment
        commitment = self.env['budget.commitment'].create_commitment(
            budget_id=self.budget_id.id,
            amount=amount,
            module_name=self._name,
            record_id=self.id,
            description=f"Commitment for {self.display_name}"
        )
        
        self.budget_commitment_id = commitment.id
        return commitment
    
    def action_release_budget_commitment(self):
        """Release budget commitment"""
        self.ensure_one()
        
        if self.budget_commitment_id:
            self.budget_commitment_id.action_release()
            self.budget_commitment_id = False
    
    def _create_overbudget_approval(self, amount):
        """Create overbudget approval workflow"""
        self.ensure_one()
        
        workflow = self.env['approval.workflow'].create({
            'name': f'Overbudget Approval: {self.display_name}',
            'workflow_type': 'overbudget',
            'amount': amount,
            'department_id': getattr(self, 'department_id', False) and self.department_id.id,
            'related_model': self._name,
            'related_record_id': self.id,
            'description': f'Overbudget approval for {self.display_name} - Amount: {amount}',
        })
        
        workflow.action_submit()
        self.overbudget_approval_id = workflow.id
        
        return workflow


# Purchase Order Integration
class PurchaseOrder(models.Model):
    _inherit = ['purchase.order', 'budget.integration.mixin']
    _name = 'purchase.order'

    # Override budget fields for Purchase Order
    budget_available = fields.Boolean('Budget Available', compute='_compute_budget_available_po')
    budget_status = fields.Text('Budget Status', compute='_compute_budget_status_po')
    
    @api.depends('budget_id', 'amount_total')
    def _compute_budget_available_po(self):
        for record in self:
            if not record.budget_id:
                record.budget_available = False
                record.is_overbudget = False
                continue
            
            is_available, message = record.budget_id.check_budget_availability(
                record.amount_total, record._name, record.id
            )
            
            record.budget_available = is_available
            record.is_overbudget = not is_available and 'overbudget' in message.lower()
    
    @api.depends('budget_id', 'amount_total')
    def _compute_budget_status_po(self):
        for record in self:
            if record.budget_id:
                status = record.budget_id.get_budget_status()
                record.budget_status = f"Budget: {status['name']} | Available: {status['available_amount']} {status['currency']} | PO Amount: {record.amount_total} {record.currency_id.name}"
            else:
                record.budget_status = "No budget assigned"
    
    def button_confirm(self):
        """Override confirm to check budget"""
        for order in self:
            if order.budget_id and order.budget_id.auto_budget_enabled:
                # Check budget availability
                is_available, message = order.budget_id.check_budget_availability(
                    order.amount_total, order._name, order.id
                )
                
                if not is_available:
                    if 'approval' in message.lower():
                        # Create overbudget approval
                        order._create_overbudget_approval(order.amount_total)
                        raise UserError(_('Purchase Order requires overbudget approval. Please wait for approval before confirming.'))
                    else:
                        raise UserError(_(message))
                
                # Create budget commitment
                order.action_create_budget_commitment()
        
        return super().button_confirm()
    
    def button_cancel(self):
        """Override cancel to release budget commitment"""
        for order in self:
            if order.budget_commitment_id:
                order.action_release_budget_commitment()
        
        return super().button_cancel()


# Sale Order Integration
class SaleOrder(models.Model):
    _inherit = ['sale.order', 'budget.integration.mixin']
    _name = 'sale.order'

    def action_confirm(self):
        """Override confirm to check budget"""
        for order in self:
            if order.budget_id and order.budget_id.auto_budget_enabled:
                # Check budget availability
                is_available, message = order.budget_id.check_budget_availability(
                    order.amount_total, order._name, order.id
                )
                
                if not is_available:
                    if 'approval' in message.lower():
                        # Create overbudget approval
                        order._create_overbudget_approval(order.amount_total)
                        raise UserError(_('Sale Order requires overbudget approval. Please wait for approval before confirming.'))
                    else:
                        raise UserError(_(message))
                
                # Create budget commitment
                order.action_create_budget_commitment()
        
        return super().action_confirm()
    
    def action_cancel(self):
        """Override cancel to release budget commitment"""
        for order in self:
            if order.budget_commitment_id:
                order.action_release_budget_commitment()
        
        return super().action_cancel()


# Account Move Integration
class AccountMove(models.Model):
    _inherit = ['account.move', 'budget.integration.mixin']
    _name = 'account.move'

    def action_post(self):
        """Override post to check budget"""
        for move in self:
            if move.budget_id and move.budget_id.auto_budget_enabled:
                # Check budget availability
                is_available, message = move.budget_id.check_budget_availability(
                    move.amount_total, move._name, move.id
                )
                
                if not is_available:
                    if 'approval' in message.lower():
                        # Create overbudget approval
                        move._create_overbudget_approval(move.amount_total)
                        raise UserError(_('Journal Entry requires overbudget approval. Please wait for approval before posting.'))
                    else:
                        raise UserError(_(message))
                
                # Create budget commitment
                move.action_create_budget_commitment()
        
        return super().action_post()
    
    def button_cancel(self):
        """Override cancel to release budget commitment"""
        for move in self:
            if move.budget_commitment_id:
                move.action_release_budget_commitment()
        
        return super().button_cancel()


# HR Expense Integration
class HrExpense(models.Model):
    _inherit = ['hr.expense', 'budget.integration.mixin']
    _name = 'hr.expense'

    def action_submit_expenses(self):
        """Override submit to check budget"""
        for expense in self:
            if expense.budget_id and expense.budget_id.auto_budget_enabled:
                # Check budget availability
                is_available, message = expense.budget_id.check_budget_availability(
                    expense.total_amount, expense._name, expense.id
                )
                
                if not is_available:
                    if 'approval' in message.lower():
                        # Create overbudget approval
                        expense._create_overbudget_approval(expense.total_amount)
                        raise UserError(_('Expense requires overbudget approval. Please wait for approval before submitting.'))
                    else:
                        raise UserError(_(message))
                
                # Create budget commitment
                expense.action_create_budget_commitment()
        
        return super().action_submit_expenses()
    
    def action_cancel(self):
        """Override cancel to release budget commitment"""
        for expense in self:
            if expense.budget_commitment_id:
                expense.action_release_budget_commitment()
        
        return super().action_cancel()


# Project Task Integration
class ProjectTask(models.Model):
    _inherit = ['project.task', 'budget.integration.mixin']
    _name = 'project.task'

    # Override amount field for tasks
    amount = fields.Float('Amount', compute='_compute_amount', store=True)
    
    @api.depends('timesheet_ids', 'timesheet_ids.amount')
    def _compute_amount(self):
        for task in self:
            task.amount = sum(task.timesheet_ids.mapped('amount'))
    
    def action_start(self):
        """Override start to check budget"""
        for task in self:
            if task.budget_id and task.budget_id.auto_budget_enabled:
                # Check budget availability
                is_available, message = task.budget_id.check_budget_availability(
                    task.amount, task._name, task.id
                )
                
                if not is_available:
                    if 'approval' in message.lower():
                        # Create overbudget approval
                        task._create_overbudget_approval(task.amount)
                        raise UserError(_('Task requires overbudget approval. Please wait for approval before starting.'))
                    else:
                        raise UserError(_(message))
                
                # Create budget commitment
                task.action_create_budget_commitment()
        
        return super().action_start()
    
    def action_cancel(self):
        """Override cancel to release budget commitment"""
        for task in self:
            if task.budget_commitment_id:
                task.action_release_budget_commitment()
        
        return super().action_cancel()


# Universal Budget Integration Service
class BudgetIntegrationService(models.Model):
    _name = 'budget.integration.service'
    _description = 'Budget Integration Service'

    @api.model
    def check_budget_for_record(self, model_name, record_id, amount=None):
        """Universal budget check for any record"""
        try:
            model = self.env[model_name]
            record = model.browse(record_id)
            
            if not record.exists():
                return False, 'Record not found'
            
            # Get amount from record
            if amount is None:
                amount = getattr(record, 'amount_total', 0) or getattr(record, 'amount', 0) or 0
            
            if amount <= 0:
                return True, 'No amount to check'
            
            # Check if record has budget integration
            if not hasattr(record, 'budget_id') or not record.budget_id:
                return True, 'No budget assigned'
            
            # Check budget availability
            is_available, message = record.budget_id.check_budget_availability(
                amount, model_name, record_id
            )
            
            return is_available, message
            
        except Exception as e:
            return False, f'Error checking budget: {str(e)}'
    
    @api.model
    def create_commitment_for_record(self, model_name, record_id, amount=None, description=''):
        """Universal commitment creation for any record"""
        try:
            model = self.env[model_name]
            record = model.browse(record_id)
            
            if not record.exists():
                return False, 'Record not found'
            
            # Get amount from record
            if amount is None:
                amount = getattr(record, 'amount_total', 0) or getattr(record, 'amount', 0) or 0
            
            if amount <= 0:
                return False, 'No amount to commit'
            
            # Check if record has budget integration
            if not hasattr(record, 'budget_id') or not record.budget_id:
                return False, 'No budget assigned'
            
            # Create commitment
            commitment = self.env['budget.commitment'].create_commitment(
                budget_id=record.budget_id.id,
                amount=amount,
                module_name=model_name,
                record_id=record_id,
                description=description or f"Commitment for {record.display_name}"
            )
            
            # Update record with commitment
            if hasattr(record, 'budget_commitment_id'):
                record.budget_commitment_id = commitment.id
            
            return True, f'Commitment created: {commitment.id}'
            
        except Exception as e:
            return False, f'Error creating commitment: {str(e)}'
    
    @api.model
    def release_commitment_for_record(self, model_name, record_id):
        """Universal commitment release for any record"""
        try:
            model = self.env[model_name]
            record = model.browse(record_id)
            
            if not record.exists():
                return False, 'Record not found'
            
            # Check if record has commitment
            if not hasattr(record, 'budget_commitment_id') or not record.budget_commitment_id:
                return True, 'No commitment to release'
            
            # Release commitment
            record.budget_commitment_id.action_release()
            record.budget_commitment_id = False
            
            return True, 'Commitment released'
            
        except Exception as e:
            return False, f'Error releasing commitment: {str(e)}'
    
    @api.model
    def get_budget_status_for_record(self, model_name, record_id):
        """Universal budget status for any record"""
        try:
            model = self.env[model_name]
            record = model.browse(record_id)
            
            if not record.exists():
                return None
            
            # Check if record has budget integration
            if not hasattr(record, 'budget_id') or not record.budget_id:
                return None
            
            return record.budget_id.get_budget_status()
            
        except Exception as e:
            return None
