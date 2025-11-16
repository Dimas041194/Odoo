# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import json
from datetime import datetime, timedelta


class DynamicUser(models.Model):
    _name = 'dynamic.user'
    _description = 'Dynamic User Management for Approval System'
    _order = 'sequence, name'
    _rec_name = 'display_name'

    name = fields.Char('User Name', required=True)
    user_id = fields.Many2one('res.users', string='Odoo User', required=True)
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    
    # User Profile
    employee_id = fields.Many2one('hr.employee', string='Employee')
    department_id = fields.Many2one('hr.department', string='Department')
    job_id = fields.Many2one('hr.job', string='Job Position')
    manager_id = fields.Many2one('hr.employee', string='Manager')
    
    # Approval Capabilities
    approval_capacity = fields.Selection([
        ('unlimited', 'Unlimited'),
        ('limited', 'Limited by Amount'),
        ('department', 'Department Based'),
        ('category', 'Category Based'),
        ('custom', 'Custom Rules')
    ], string='Approval Capacity', required=True, default='unlimited')
    
    # Approval Limits
    max_approval_amount = fields.Float('Maximum Approval Amount', default=0.0)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    approval_categories = fields.Many2many('product.category', string='Approval Categories')
    approval_departments = fields.Many2many('hr.department', string='Approval Departments')
    
    # Custom Rules
    custom_rules = fields.Text('Custom Approval Rules', help='JSON format for custom approval rules')
    rule_conditions = fields.Text('Rule Conditions', help='JSON format for rule conditions')
    
    # Availability and Schedule
    available_hours = fields.Char('Available Hours', default='09:00-17:00', help='Format: HH:MM-HH:MM')
    available_days = fields.Selection([
        ('weekdays', 'Weekdays Only'),
        ('weekends', 'Weekends Only'),
        ('all_days', 'All Days'),
        ('custom', 'Custom Days')
    ], string='Available Days', default='weekdays')
    custom_days = fields.Char('Custom Days', help='Comma separated: mon,tue,wed,thu,fri,sat,sun')
    
    # Delegation and Backup
    delegate_to_id = fields.Many2one('dynamic.user', string='Delegate To')
    backup_user_ids = fields.Many2many(
    'dynamic.user',
    'dynamic_user_backup_rel',  # Sudah unik, biarkan
    'user_id',
    'backup_id',
    string='Backup Users'
)
    auto_delegate = fields.Boolean('Auto Delegate When Unavailable', default=False)
    delegation_rules = fields.Text('Delegation Rules', help='JSON format for delegation rules')
    
    # Notification Preferences
    email_notifications = fields.Boolean('Email Notifications', default=True)
    sms_notifications = fields.Boolean('SMS Notifications', default=False)
    push_notifications = fields.Boolean('Push Notifications', default=True)
    notification_frequency = fields.Selection([
        ('immediate', 'Immediate'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly')
    ], string='Notification Frequency', default='immediate')
    
    # Approval Statistics
    total_approvals = fields.Integer('Total Approvals', compute='_compute_approval_stats')
    pending_approvals = fields.Integer('Pending Approvals', compute='_compute_approval_stats')
    approved_count = fields.Integer('Approved Count', compute='_compute_approval_stats')
    rejected_count = fields.Integer('Rejected Count', compute='_compute_approval_stats')
    average_approval_time = fields.Float('Average Approval Time (Hours)', compute='_compute_approval_stats')
    
    # Status and Availability
    current_status = fields.Selection([
        ('available', 'Available'),
        ('busy', 'Busy'),
        ('away', 'Away'),
        ('offline', 'Offline'),
        ('delegated', 'Delegated')
    ], string='Current Status', default='available')
    
    last_activity = fields.Datetime('Last Activity')
    is_online = fields.Boolean('Is Online', compute='_compute_is_online')
    
    # Workflow Relations
    approval_ids = fields.One2many('approval.workflow.approval', 'approver_id', string='Approvals')
    delegated_approval_ids = fields.One2many('approval.workflow.approval', 'delegated_to_id', string='Delegated Approvals')
    
    @api.depends('name', 'user_id.name')
    def _compute_display_name(self):
        for record in self:
            if record.user_id:
                record.display_name = f"{record.name} ({record.user_id.name})"
            else:
                record.display_name = record.name
    
    @api.depends('approval_ids', 'delegated_approval_ids')
    def _compute_approval_stats(self):
        for record in self:
            all_approvals = record.approval_ids | record.delegated_approval_ids
            record.total_approvals = len(all_approvals)
            record.pending_approvals = len(all_approvals.filtered(lambda a: a.state == 'pending'))
            record.approved_count = len(all_approvals.filtered(lambda a: a.state == 'approved'))
            record.rejected_count = len(all_approvals.filtered(lambda a: a.state == 'rejected'))
            
            # Calculate average approval time
            approved_approvals = all_approvals.filtered(lambda a: a.state == 'approved' and a.approved_date)
            if approved_approvals:
                total_time = sum([
                    (a.approved_date - a.create_date).total_seconds() / 3600
                    for a in approved_approvals
                ])
                record.average_approval_time = total_time / len(approved_approvals)
            else:
                record.average_approval_time = 0.0
    
    @api.depends('last_activity')
    def _compute_is_online(self):
        now = fields.Datetime.now()
        for record in self:
            if record.last_activity:
                time_diff = (now - record.last_activity).total_seconds() / 60  # minutes
                record.is_online = time_diff < 15  # Consider online if activity within 15 minutes
            else:
                record.is_online = False
    
    @api.constrains('max_approval_amount')
    def _check_approval_amount(self):
        for record in self:
            if record.approval_capacity == 'limited' and record.max_approval_amount <= 0:
                raise ValidationError(_('Maximum approval amount must be greater than 0 for limited capacity.'))
    
    @api.constrains('available_hours')
    def _check_available_hours(self):
        for record in self:
            if record.available_hours:
                try:
                    start_time, end_time = record.available_hours.split('-')
                    datetime.strptime(start_time.strip(), '%H:%M')
                    datetime.strptime(end_time.strip(), '%H:%M')
                except ValueError:
                    raise ValidationError(_('Available hours must be in format HH:MM-HH:MM'))
    
    def action_update_activity(self):
        """Update user activity timestamp"""
        self.write({'last_activity': fields.Datetime.now()})
        return True
    
    def action_set_status(self, status):
        """Set user status"""
        self.write({'current_status': status})
        return True
    
    def is_available_now(self):
        """Check if user is available at current time"""
        if not self.active or self.current_status in ['offline', 'delegated']:
            return False
        
        # Check if user is online
        if not self.is_online:
            return False
        
        # Check available hours
        if self.available_hours:
            now = datetime.now()
            current_time = now.strftime('%H:%M')
            start_time, end_time = self.available_hours.split('-')
            
            if not (start_time.strip() <= current_time <= end_time.strip()):
                return False
        
        # Check available days
        if self.available_days == 'weekdays' and now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        elif self.available_days == 'weekends' and now.weekday() < 5:
            return False
        elif self.available_days == 'custom' and self.custom_days:
            day_names = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
            current_day = day_names[now.weekday()]
            if current_day not in self.custom_days.lower():
                return False
        
        return True
    
    def can_approve_amount(self, amount):
        """Check if user can approve specific amount"""
        if self.approval_capacity == 'unlimited':
            return True
        elif self.approval_capacity == 'limited':
            return amount <= self.max_approval_amount
        elif self.approval_capacity == 'department':
            # Check department-based rules
            return True  # Implement department logic
        elif self.approval_capacity == 'category':
            # Check category-based rules
            return True  # Implement category logic
        elif self.approval_capacity == 'custom':
            # Check custom rules
            return self._check_custom_approval_rules(amount)
        
        return False
    
    def _check_custom_approval_rules(self, amount):
        """Check custom approval rules"""
        if not self.custom_rules:
            return True
        
        try:
            rules = json.loads(self.custom_rules)
            for rule in rules:
                if rule.get('type') == 'amount' and amount > rule.get('max_amount', 0):
                    return False
                elif rule.get('type') == 'department' and not self._check_department_rule(rule):
                    return False
                elif rule.get('type') == 'category' and not self._check_category_rule(rule):
                    return False
        except (json.JSONDecodeError, KeyError):
            return True
        
        return True
    
    def _check_department_rule(self, rule):
        """Check department-based rule"""
        required_departments = rule.get('departments', [])
        if required_departments and self.department_id.id not in required_departments:
            return False
        return True
    
    def _check_category_rule(self, rule):
        """Check category-based rule"""
        required_categories = rule.get('categories', [])
        if required_categories and not any(cat in self.approval_categories.ids for cat in required_categories):
            return False
        return True
    
    def get_delegation_user(self, workflow_data=None):
        """Get appropriate delegation user"""
        if not self.auto_delegate:
            return False
        
        # Check delegation rules
        if self.delegation_rules:
            try:
                rules = json.loads(self.delegation_rules)
                for rule in rules:
                    if self._check_delegation_rule(rule, workflow_data):
                        return self.env['dynamic.user'].browse(rule.get('delegate_to_id'))
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Default delegation
        if self.delegate_to_id and self.delegate_to_id.is_available_now():
            return self.delegate_to_id
        
        # Check backup users
        for backup_user in self.backup_user_ids:
            if backup_user.is_available_now():
                return backup_user
        
        return False
    
    def _check_delegation_rule(self, rule, workflow_data):
        """Check if delegation rule applies"""
        if rule.get('type') == 'amount' and workflow_data:
            amount = workflow_data.get('amount', 0)
            if amount > rule.get('max_amount', 0):
                return True
        elif rule.get('type') == 'department' and workflow_data:
            department_id = workflow_data.get('department_id')
            if department_id in rule.get('departments', []):
                return True
        elif rule.get('type') == 'time' and rule.get('timeout_hours', 0) > 0:
            # Check if user has been unavailable for specified time
            if self.last_activity:
                time_diff = (fields.Datetime.now() - self.last_activity).total_seconds() / 3600
                return time_diff > rule.get('timeout_hours', 0)
        
        return False
    
    def send_notification(self, message, notification_type='email', priority='normal'):
        """Send notification to user"""
        if notification_type == 'email' and self.email_notifications:
            self._send_email_notification(message, priority)
        elif notification_type == 'sms' and self.sms_notifications:
            self._send_sms_notification(message, priority)
        elif notification_type == 'push' and self.push_notifications:
            self._send_push_notification(message, priority)
    
    def _send_email_notification(self, message, priority):
        """Send email notification"""
        # Implementation for email notification
        pass
    
    def _send_sms_notification(self, message, priority):
        """Send SMS notification"""
        # Implementation for SMS notification
        pass
    
    def _send_push_notification(self, message, priority):
        """Send push notification"""
        # Implementation for push notification
        pass
    
    @api.model
    def get_available_approvers(self, criteria=None):
        """Get list of available approvers based on criteria"""
        domain = [('active', '=', True)]
        
        if criteria:
            if criteria.get('amount'):
                domain.append(('max_approval_amount', '>=', criteria['amount']))
            if criteria.get('department_id'):
                domain.append(('approval_departments', 'in', [criteria['department_id']]))
            if criteria.get('category_id'):
                domain.append(('approval_categories', 'in', [criteria['category_id']]))
        
        approvers = self.search(domain)
        return approvers.filtered(lambda u: u.is_available_now())
    
    def action_view_approvals(self):
        """View user's approvals"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('User Approvals'),
            'res_model': 'approval.workflow.approval',
            'view_mode': 'tree,form',
            'domain': [('approver_id', '=', self.id)],
            'context': {'default_approver_id': self.id},
        }
