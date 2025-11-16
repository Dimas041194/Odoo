# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import json
from datetime import datetime, timedelta


class BudgetNotificationTemplate(models.Model):
    _name = 'budget.notification.template'
    _description = 'Budget Notification Template'
    _order = 'name'

    name = fields.Char('Template Name', required=True)
    template_type = fields.Selection([
        ('overbudget_alert', 'Overbudget Alert'),
        ('threshold_warning', 'Threshold Warning'),
        ('threshold_danger', 'Threshold Danger'),
        ('threshold_critical', 'Threshold Critical'),
        ('budget_approved', 'Budget Approved'),
        ('budget_rejected', 'Budget Rejected'),
        ('commitment_created', 'Commitment Created'),
        ('commitment_released', 'Commitment Released'),
        ('budget_closed', 'Budget Closed'),
        ('custom', 'Custom')
    ], string='Template Type', required=True)
    
    # Template Content
    subject = fields.Char('Subject', required=True, translate=True)
    body_html = fields.Html('Body (HTML)', translate=True)
    body_text = fields.Text('Body (Text)', translate=True)
    
    # Recipients
    recipient_type = fields.Selection([
        ('budget_manager', 'Budget Manager'),
        ('department_manager', 'Department Manager'),
        ('finance_team', 'Finance Team'),
        ('approvers', 'Approvers'),
        ('custom', 'Custom')
    ], string='Recipient Type', required=True, default='budget_manager')
    
    custom_recipients = fields.Text('Custom Recipients', help='JSON format: [{"type": "email", "value": "email@example.com"}]')
    
    # Conditions
    threshold_percentage_min = fields.Float('Minimum Threshold %')
    threshold_percentage_max = fields.Float('Maximum Threshold %')
    budget_amount_min = fields.Float('Minimum Budget Amount')
    budget_amount_max = fields.Float('Maximum Budget Amount')
    #department_ids = fields.Many2many('hr.department', string='Applicable Departments')
    
    # Settings
    active = fields.Boolean('Active', default=True)
    send_immediately = fields.Boolean('Send Immediately', default=True)
    delay_minutes = fields.Integer('Delay (Minutes)', default=0)
    
    # Statistics
    sent_count = fields.Integer('Sent Count', compute='_compute_statistics')
    opened_count = fields.Integer('Opened Count', compute='_compute_statistics')
    
    @api.depends('notification_log_ids')
    def _compute_statistics(self):
        for record in self:
            logs = record.notification_log_ids
            record.sent_count = len(logs)
            record.opened_count = len(logs.filtered(lambda l: l.opened_date))
    
    def render_template(self, budget_data, alert_data=None, commitment_data=None):
        """Render template with data"""
        template_vars = {
            'budget': budget_data,
            'alert': alert_data or {},
            'commitment': commitment_data or {},
            'company': self.env.company,
            'user': self.env.user,
            'date': fields.Datetime.now(),
        }
        
        # Render subject
        subject = self._render_text(self.subject, template_vars)
        
        # Render body
        body_html = self._render_text(self.body_html, template_vars) if self.body_html else ''
        body_text = self._render_text(self.body_text, template_vars) if self.body_text else ''
        
        return {
            'subject': subject,
            'body_html': body_html,
            'body_text': body_text,
        }
    
    def _render_text(self, text, variables):
        """Render text with variables"""
        if not text:
            return ''
        
        rendered = text
        for key, value in variables.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    placeholder = f'{{{{{key}.{sub_key}}}}}'
                    rendered = rendered.replace(placeholder, str(sub_value or ''))
            else:
                placeholder = f'{{{{{key}}}}}'
                rendered = rendered.replace(placeholder, str(value or ''))
        
        return rendered
    
    def check_conditions(self, budget_data, alert_data=None):
        """Check if template conditions are met"""
        # Check threshold percentage
        if self.threshold_percentage_min and alert_data:
            if alert_data.get('threshold_percentage', 0) < self.threshold_percentage_min:
                return False
        
        if self.threshold_percentage_max and alert_data:
            if alert_data.get('threshold_percentage', 0) > self.threshold_percentage_max:
                return False
        
        # Check budget amount
        if self.budget_amount_min and budget_data.get('total_budget', 0) < self.budget_amount_min:
            return False
        
        if self.budget_amount_max and budget_data.get('total_budget', 0) > self.budget_amount_max:
            return False
        
        # Check department
        if self.department_ids and budget_data.get('department_id') not in self.department_ids.ids:
            return False
        
        return True


class BudgetNotificationLog(models.Model):
    _name = 'budget.notification.log'
    _description = 'Budget Notification Log'
    _order = 'create_date desc'

    template_id = fields.Many2one('budget.notification.template', string='Template', required=True)
    budget_id = fields.Many2one('budget.management', string='Budget')
    alert_id = fields.Many2one('budget.alert', string='Alert')
    commitment_id = fields.Many2one('budget.commitment', string='Commitment')
    
    # Recipient Information
    recipient_email = fields.Char('Recipient Email')
    recipient_user_id = fields.Many2one('res.users', string='Recipient User')
    
    # Message Content
    subject = fields.Char('Subject')
    body_html = fields.Html('Body (HTML)')
    body_text = fields.Text('Body (Text)')
    
    # Status and Tracking
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('opened', 'Opened'),
        ('clicked', 'Clicked'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced')
    ], string='Status', default='draft')
    
    sent_date = fields.Datetime('Sent Date')
    delivered_date = fields.Datetime('Delivered Date')
    opened_date = fields.Datetime('Opened Date')
    clicked_date = fields.Datetime('Clicked Date')
    
    # Error Information
    error_message = fields.Text('Error Message')
    retry_count = fields.Integer('Retry Count', default=0)
    
    def action_send(self):
        """Send the notification"""
        self.ensure_one()
        
        try:
            if self.recipient_email:
                self._send_email()
            elif self.recipient_user_id:
                self._send_internal_message()
            
            self.write({
                'state': 'sent',
                'sent_date': fields.Datetime.now()
            })
            
        except Exception as e:
            self.write({
                'state': 'failed',
                'error_message': str(e),
                'retry_count': self.retry_count + 1
            })
    
    def _send_email(self):
        """Send email notification"""
        if not self.recipient_email:
            raise UserError(_('Recipient email is required for email notifications.'))
        
        # Create mail message
        mail_values = {
            'subject': self.subject,
            'body_html': self.body_html,
            'email_to': self.recipient_email,
            'auto_delete': True,
        }
        
        mail = self.env['mail.mail'].create(mail_values)
        mail.send()
    
    def _send_internal_message(self):
        """Send internal message"""
        if not self.recipient_user_id:
            raise UserError(_('Recipient user is required for internal messages.'))
        
        # Create internal message
        message_values = {
            'subject': self.subject,
            'body': self.body_text or self.body_html,
            'partner_ids': [(4, self.recipient_user_id.partner_id.id)],
            'subtype_id': self.env.ref('mail.mt_comment').id,
        }
        
        message = self.env['mail.message'].create(message_values)
    
    def action_mark_opened(self):
        """Mark notification as opened"""
        self.write({
            'state': 'opened',
            'opened_date': fields.Datetime.now()
        })


class BudgetNotificationService(models.Model):
    _name = 'budget.notification.service'
    _description = 'Budget Notification Service'

    @api.model
    def send_overbudget_notification(self, budget_id, alert_id, amount, module_name, record_id):
        """Send overbudget notification"""
        budget = self.env['budget.management'].browse(budget_id)
        alert = self.env['budget.alert'].browse(alert_id)
        
        if not budget.exists() or not alert.exists():
            return False
        
        # Find applicable template
        template = self.env['budget.notification.template'].search([
            ('template_type', '=', 'overbudget_alert'),
            ('active', '=', True)
        ])
        
        if not template:
            # Create default template
            template = self._create_default_overbudget_template()
        
        # Prepare data
        budget_data = budget.get_budget_status()
        alert_data = alert.get_alert_status()
        
        # Check conditions
        if not template.check_conditions(budget_data, alert_data):
            return False
        
        # Get recipients
        recipients = self._get_notification_recipients(template, budget)
        
        # Send notifications
        for recipient in recipients:
            self._send_notification(template, recipient, budget_data, alert_data)
        
        return True
    
    @api.model
    def send_threshold_notification(self, budget_id, alert_id, threshold_percentage):
        """Send threshold notification"""
        budget = self.env['budget.management'].browse(budget_id)
        alert = self.env['budget.alert'].browse(alert_id)
        
        if not budget.exists() or not alert.exists():
            return False
        
        # Determine template type based on threshold
        template_type = 'threshold_warning'
        if threshold_percentage >= 100:
            template_type = 'threshold_critical'
        elif threshold_percentage >= 95:
            template_type = 'threshold_danger'
        
        # Find applicable template
        template = self.env['budget.notification.template'].search([
            ('template_type', '=', template_type),
            ('active', '=', True)
        ])
        
        if not template:
            # Create default template
            template = self._create_default_threshold_template(template_type)
        
        # Prepare data
        budget_data = budget.get_budget_status()
        alert_data = alert.get_alert_status()
        
        # Check conditions
        if not template.check_conditions(budget_data, alert_data):
            return False
        
        # Get recipients
        recipients = self._get_notification_recipients(template, budget)
        
        # Send notifications
        for recipient in recipients:
            self._send_notification(template, recipient, budget_data, alert_data)
        
        return True
    
    @api.model
    def send_commitment_notification(self, commitment_id, notification_type='created'):
        """Send commitment notification"""
        commitment = self.env['budget.commitment'].browse(commitment_id)
        
        if not commitment.exists():
            return False
        
        # Find applicable template
        template_type = f'commitment_{notification_type}'
        template = self.env['budget.notification.template'].search([
            ('template_type', '=', template_type),
            ('active', '=', True)
        ])
        
        if not template:
            # Create default template
            template = self._create_default_commitment_template(template_type)
        
        # Prepare data
        budget_data = commitment.budget_id.get_budget_status()
        commitment_data = commitment.get_commitment_status()
        
        # Check conditions
        if not template.check_conditions(budget_data, commitment_data):
            return False
        
        # Get recipients
        recipients = self._get_notification_recipients(template, commitment.budget_id)
        
        # Send notifications
        for recipient in recipients:
            self._send_notification(template, recipient, budget_data, commitment_data)
        
        return True
    
    def _get_notification_recipients(self, template, budget):
        """Get notification recipients based on template configuration"""
        recipients = []
        
        if template.recipient_type == 'budget_manager':
            # Get budget managers
            managers = self.env['res.users'].search([
                ('groups_id', 'in', [self.env.ref('budget_management.group_budget_manager').id])
            ])
            for manager in managers:
                recipients.append({
                    'type': 'email',
                    'email': manager.email,
                    'user_id': manager.id,
                })
        
        elif template.recipient_type == 'department_manager':
            # Get department managers
            if budget.department_id and budget.department_id.manager_id:
                manager = budget.department_id.manager_id.user_id
                if manager:
                    recipients.append({
                        'type': 'email',
                        'email': manager.email,
                        'user_id': manager.id,
                    })
        
        elif template.recipient_type == 'finance_team':
            # Get finance team
            finance_users = self.env['res.users'].search([
                ('groups_id', 'in', [self.env.ref('account.group_account_manager').id])
            ])
            for user in finance_users:
                recipients.append({
                    'type': 'email',
                    'email': user.email,
                    'user_id': user.id,
                })
        
        elif template.recipient_type == 'approvers':
            # Get budget approvers
            if budget.approval_workflow_id:
                approvers = budget.approval_workflow_id.approval_ids.mapped('approver_id.user_id')
                for approver in approvers:
                    if approver:
                        recipients.append({
                            'type': 'email',
                            'email': approver.email,
                            'user_id': approver.id,
                        })
        
        elif template.recipient_type == 'custom' and template.custom_recipients:
            try:
                custom_recipients = json.loads(template.custom_recipients)
                recipients.extend(custom_recipients)
            except (json.JSONDecodeError, KeyError):
                pass
        
        return recipients
    
    def _send_notification(self, template, recipient, budget_data, additional_data=None):
        """Send notification to recipient"""
        # Render template
        rendered = template.render_template(budget_data, additional_data)
        
        # Create notification log
        log_values = {
            'template_id': template.id,
            'budget_id': budget_data.get('budget_id'),
            'recipient_email': recipient.get('email'),
            'recipient_user_id': recipient.get('user_id'),
            'subject': rendered['subject'],
            'body_html': rendered['body_html'],
            'body_text': rendered['body_text'],
        }
        
        log = self.env['budget.notification.log'].create(log_values)
        log.action_send()
    
    def _create_default_overbudget_template(self):
        """Create default overbudget template"""
        return self.env['budget.notification.template'].create({
            'name': 'Overbudget Alert',
            'template_type': 'overbudget_alert',
            'recipient_type': 'budget_manager',
            'subject': 'Overbudget Alert: {{budget.name}}',
            'body_html': '''
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #dc3545;">Overbudget Alert</h2>
                    <p>Dear Manager,</p>
                    <p>An overbudget situation has been detected in the budget system.</p>
                    
                    <div style="background-color: #f8d7da; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #dc3545;">
                        <h3 style="margin-top: 0; color: #721c24;">Budget Details</h3>
                        <p><strong>Budget:</strong> {{budget.name}}</p>
                        <p><strong>Department:</strong> {{budget.department}}</p>
                        <p><strong>Total Budget:</strong> {{budget.total_budget}} {{budget.currency}}</p>
                        <p><strong>Committed Amount:</strong> {{budget.committed_amount}} {{budget.currency}}</p>
                        <p><strong>Available Amount:</strong> {{budget.available_amount}} {{budget.currency}}</p>
                        <p><strong>Overbudget Amount:</strong> {{alert.amount}} {{budget.currency}}</p>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="/web#id={{budget.budget_id}}&model=budget.management&view_type=form" 
                           style="background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                            View Budget
                        </a>
                    </div>
                </div>
            ''',
            'body_text': '''
                Overbudget Alert: {{budget.name}}
                
                Dear Manager,
                
                An overbudget situation has been detected in the budget system.
                
                Budget Details:
                - Budget: {{budget.name}}
                - Department: {{budget.department}}
                - Total Budget: {{budget.total_budget}} {{budget.currency}}
                - Committed Amount: {{budget.committed_amount}} {{budget.currency}}
                - Available Amount: {{budget.available_amount}} {{budget.currency}}
                - Overbudget Amount: {{alert.amount}} {{budget.currency}}
                
                Please review the budget and take appropriate action.
            ''',
            'active': True,
        })
    
    def _create_default_threshold_template(self, template_type):
        """Create default threshold template"""
        colors = {
            'threshold_warning': '#ffc107',
            'threshold_danger': '#fd7e14',
            'threshold_critical': '#dc3545'
        }
        
        titles = {
            'threshold_warning': 'Budget Warning',
            'threshold_danger': 'Budget Danger',
            'threshold_critical': 'Budget Critical'
        }
        
        return self.env['budget.notification.template'].create({
            'name': titles[template_type],
            'template_type': template_type,
            'recipient_type': 'budget_manager',
            'subject': f'{titles[template_type]}: {{budget.name}}',
            'body_html': f'''
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: {colors[template_type]};">{titles[template_type]}</h2>
                    <p>Dear Manager,</p>
                    <p>A budget threshold has been reached.</p>
                    
                    <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid {colors[template_type]};">
                        <h3 style="margin-top: 0; color: #856404;">Budget Details</h3>
                        <p><strong>Budget:</strong> {{budget.name}}</p>
                        <p><strong>Department:</strong> {{budget.department}}</p>
                        <p><strong>Total Budget:</strong> {{budget.total_budget}} {{budget.currency}}</p>
                        <p><strong>Committed Amount:</strong> {{budget.committed_amount}} {{budget.currency}}</p>
                        <p><strong>Utilization:</strong> {{budget.utilization_percentage}}%</p>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="/web#id={{budget.budget_id}}&model=budget.management&view_type=form" 
                           style="background-color: {colors[template_type]}; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                            View Budget
                        </a>
                    </div>
                </div>
            ''',
            'active': True,
        })
    
    def _create_default_commitment_template(self, template_type):
        """Create default commitment template"""
        return self.env['budget.notification.template'].create({
            'name': f'Commitment {template_type.title()}',
            'template_type': template_type,
            'recipient_type': 'budget_manager',
            'subject': f'Commitment {template_type.title()}: {{budget.name}}',
            'body_html': f'''
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #007bff;">Commitment {template_type.title()}</h2>
                    <p>Dear Manager,</p>
                    <p>A budget commitment has been {template_type}.</p>
                    
                    <div style="background-color: #d1ecf1; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #007bff;">
                        <h3 style="margin-top: 0; color: #0c5460;">Commitment Details</h3>
                        <p><strong>Budget:</strong> {{budget.name}}</p>
                        <p><strong>Amount:</strong> {{commitment.amount}} {{budget.currency}}</p>
                        <p><strong>Description:</strong> {{commitment.description}}</p>
                        <p><strong>Module:</strong> {{commitment.module_name}}</p>
                        <p><strong>Record:</strong> {{commitment.record_name}}</p>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="/web#id={{budget.budget_id}}&model=budget.management&view_type=form" 
                           style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                            View Budget
                        </a>
                    </div>
                </div>
            ''',
            'active': True,
        })
