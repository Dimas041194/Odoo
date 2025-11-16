# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import json
from datetime import datetime, timedelta


class NotificationTemplate(models.Model):
    _name = 'notification.template'
    _description = 'Email Notification Template'
    _order = 'name'

    name = fields.Char('Template Name', required=True)
    subject = fields.Char('Subject', required=True, translate=True)
    body_html = fields.Html('Body (HTML)', translate=True)
    body_text = fields.Text('Body (Text)', translate=True)
    active = fields.Boolean('Active', default=True)
    
    # Template Configuration
    template_type = fields.Selection([
        ('approval_request', 'Approval Request'),
        ('approval_reminder', 'Approval Reminder'),
        ('approval_approved', 'Approval Approved'),
        ('approval_rejected', 'Approval Rejected'),
        ('approval_escalated', 'Approval Escalated'),
        ('approval_delegated', 'Approval Delegated'),
        ('approval_timeout', 'Approval Timeout'),
        ('workflow_completed', 'Workflow Completed'),
        ('workflow_cancelled', 'Workflow Cancelled'),
        ('custom', 'Custom')
    ], string='Template Type', required=True)
    
    # Recipients Configuration
    recipient_type = fields.Selection([
        ('approver', 'Approver'),
        ('requester', 'Requester'),
        ('manager', 'Manager'),
        ('department', 'Department'),
        ('custom', 'Custom')
    ], string='Recipient Type', required=True, default='approver')
    
    custom_recipients = fields.Text('Custom Recipients', help='JSON format: [{"type": "email", "value": "email@example.com"}]')
    
    # Template Variables
    available_variables = fields.Text('Available Variables', 
        default='{{workflow.name}}, {{workflow.amount}}, {{workflow.requester}}, {{approver.name}}, {{approval.deadline}}')
    
    # Language and Localization
    lang = fields.Selection('_get_languages', string='Language', default='en_US')
    
    # Scheduling
    send_immediately = fields.Boolean('Send Immediately', default=True)
    delay_hours = fields.Integer('Delay (Hours)', default=0)
    send_time = fields.Char('Send Time', help='Format: HH:MM (24-hour)')
    
    # Conditions
    condition_amount_min = fields.Float('Minimum Amount')
    condition_amount_max = fields.Float('Maximum Amount')
    condition_department_ids = fields.Many2many('hr.department', string='Required Departments')
    condition_category_ids = fields.Many2many('product.category', string='Required Categories')
    custom_conditions = fields.Text('Custom Conditions', help='JSON format for custom conditions')
    
    # Statistics
    sent_count = fields.Integer('Sent Count', compute='_compute_statistics')
    opened_count = fields.Integer('Opened Count', compute='_compute_statistics')
    clicked_count = fields.Integer('Clicked Count', compute='_compute_statistics')
    
    @api.model
    def _get_languages(self):
        return self.env['res.lang'].get_installed()
    
    @api.depends('notification_log_ids')
    def _compute_statistics(self):
        for record in self:
            logs = record.notification_log_ids
            record.sent_count = len(logs)
            record.opened_count = len(logs.filtered(lambda l: l.opened_date))
            record.clicked_count = len(logs.filtered(lambda l: l.clicked_date))
    
    def render_template(self, workflow_data, approver_data=None, approval_data=None):
        """Render template with data"""
        template_vars = {
            'workflow': workflow_data,
            'approver': approver_data or {},
            'approval': approval_data or {},
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
    
    def check_conditions(self, workflow_data):
        """Check if template conditions are met"""
        if self.condition_amount_min and workflow_data.get('amount', 0) < self.condition_amount_min:
            return False
        
        if self.condition_amount_max and workflow_data.get('amount', 0) > self.condition_amount_max:
            return False
        
        if self.condition_department_ids and workflow_data.get('department_id') not in self.condition_department_ids.ids:
            return False
        
        if self.condition_category_ids and workflow_data.get('category_id') not in self.condition_category_ids.ids:
            return False
        
        if self.custom_conditions:
            try:
                conditions = json.loads(self.custom_conditions)
                for condition in conditions:
                    if not self._check_custom_condition(condition, workflow_data):
                        return False
            except (json.JSONDecodeError, KeyError):
                pass
        
        return True
    
    def _check_custom_condition(self, condition, workflow_data):
        """Check custom condition"""
        field = condition.get('field')
        operator = condition.get('operator')
        value = condition.get('value')
        
        if not all([field, operator, value]):
            return True
        
        field_value = self._get_field_value(field, workflow_data)
        
        if operator == 'eq':
            return field_value == value
        elif operator == 'ne':
            return field_value != value
        elif operator == 'gt':
            return field_value > value
        elif operator == 'lt':
            return field_value < value
        elif operator == 'gte':
            return field_value >= value
        elif operator == 'lte':
            return field_value <= value
        elif operator == 'in':
            return field_value in value
        elif operator == 'not_in':
            return field_value not in value
        elif operator == 'contains':
            return value in str(field_value)
        
        return True
    
    def _get_field_value(self, field_path, data):
        """Get field value from nested data"""
        keys = field_path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value


class NotificationLog(models.Model):
    _name = 'notification.log'
    _description = 'Notification Log'
    _order = 'create_date desc'

    template_id = fields.Many2one('notification.template', string='Template', required=True)
    workflow_id = fields.Many2one('approval.workflow', string='Workflow')
    approval_id = fields.Many2one('approval.workflow.approval', string='Approval')
    
    # Recipient Information
    recipient_type = fields.Selection([
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('internal', 'Internal Message')
    ], string='Recipient Type', required=True)
    
    recipient_email = fields.Char('Recipient Email')
    recipient_phone = fields.Char('Recipient Phone')
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
    max_retries = fields.Integer('Max Retries', default=3)
    
    # Response Data
    response_data = fields.Text('Response Data', help='JSON format for response data')
    
    def action_send(self):
        """Send the notification"""
        self.ensure_one()
        
        try:
            if self.recipient_type == 'email':
                self._send_email()
            elif self.recipient_type == 'sms':
                self._send_sms()
            elif self.recipient_type == 'push':
                self._send_push()
            elif self.recipient_type == 'internal':
                self._send_internal()
            
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
    
    def _send_sms(self):
        """Send SMS notification"""
        if not self.recipient_phone:
            raise UserError(_('Recipient phone is required for SMS notifications.'))
        
        # Implementation for SMS sending
        # This would integrate with SMS gateway
        pass
    
    def _send_push(self):
        """Send push notification"""
        if not self.recipient_user_id:
            raise UserError(_('Recipient user is required for push notifications.'))
        
        # Implementation for push notification
        # This would integrate with push notification service
        pass
    
    def _send_internal(self):
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
    
    def action_mark_clicked(self):
        """Mark notification as clicked"""
        self.write({
            'state': 'clicked',
            'clicked_date': fields.Datetime.now()
        })
    
    def action_retry(self):
        """Retry sending notification"""
        if self.retry_count < self.max_retries:
            self.action_send()
        else:
            raise UserError(_('Maximum retry attempts reached.'))


class NotificationQueue(models.Model):
    _name = 'notification.queue'
    _description = 'Notification Queue'
    _order = 'priority desc, scheduled_date'

    template_id = fields.Many2one('notification.template', string='Template', required=True)
    workflow_id = fields.Many2one('approval.workflow', string='Workflow')
    approval_id = fields.Many2one('approval.workflow.approval', string='Approval')
    
    # Queue Configuration
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], string='Priority', default='normal')
    
    scheduled_date = fields.Datetime('Scheduled Date', required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], string='State', default='pending')
    
    # Recipient Data
    recipient_data = fields.Text('Recipient Data', help='JSON format for recipient information')
    
    # Message Data
    message_data = fields.Text('Message Data', help='JSON format for message content')
    
    # Processing Information
    processed_date = fields.Datetime('Processed Date')
    error_message = fields.Text('Error Message')
    retry_count = fields.Integer('Retry Count', default=0)
    
    def action_process(self):
        """Process queued notification"""
        self.ensure_one()
        
        if self.state != 'pending':
            return
        
        self.write({'state': 'processing'})
        
        try:
            # Parse recipient data
            recipient_data = json.loads(self.recipient_data) if self.recipient_data else {}
            message_data = json.loads(self.message_data) if self.message_data else {}
            
            # Create notification log
            log_values = {
                'template_id': self.template_id.id,
                'workflow_id': self.workflow_id.id if self.workflow_id else False,
                'approval_id': self.approval_id.id if self.approval_id else False,
                'recipient_type': recipient_data.get('type', 'email'),
                'recipient_email': recipient_data.get('email'),
                'recipient_phone': recipient_data.get('phone'),
                'recipient_user_id': recipient_data.get('user_id'),
                'subject': message_data.get('subject'),
                'body_html': message_data.get('body_html'),
                'body_text': message_data.get('body_text'),
            }
            
            log = self.env['notification.log'].create(log_values)
            log.action_send()
            
            self.write({
                'state': 'sent',
                'processed_date': fields.Datetime.now()
            })
            
        except Exception as e:
            self.write({
                'state': 'failed',
                'error_message': str(e),
                'retry_count': self.retry_count + 1
            })
    
    @api.model
    def process_queue(self):
        """Process all pending notifications in queue"""
        pending_notifications = self.search([
            ('state', '=', 'pending'),
            ('scheduled_date', '<=', fields.Datetime.now())
        ])
        
        for notification in pending_notifications:
            notification.action_process()
    
    def action_cancel(self):
        """Cancel queued notification"""
        self.write({'state': 'cancelled'})
