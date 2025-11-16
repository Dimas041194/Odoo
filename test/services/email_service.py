# -*- coding: utf-8 -*-

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging
from datetime import datetime, timedelta
import json

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.addons.base.models.ir_mail_server import MailDeliveryException

_logger = logging.getLogger(__name__)


class EmailService(models.Model):
    _name = 'email.service'
    _description = 'Email Service for Notifications'
    _rec_name = 'name'

    name = fields.Char('Service Name', required=True)
    active = fields.Boolean('Active', default=True)
    
    # SMTP Configuration
    smtp_server = fields.Char('SMTP Server', required=True)
    smtp_port = fields.Integer('SMTP Port', default=587)
    smtp_user = fields.Char('SMTP Username')
    smtp_password = fields.Char('SMTP Password')
    smtp_encryption = fields.Selection([
        ('none', 'None'),
        ('tls', 'TLS'),
        ('ssl', 'SSL')
    ], string='Encryption', default='tls')
    
    # Email Configuration
    from_email = fields.Char('From Email', required=True)
    from_name = fields.Char('From Name')
    reply_to = fields.Char('Reply To Email')
    
    # Rate Limiting
    max_emails_per_hour = fields.Integer('Max Emails Per Hour', default=100)
    max_emails_per_day = fields.Integer('Max Emails Per Day', default=1000)
    
    # Statistics
    emails_sent_today = fields.Integer('Emails Sent Today', compute='_compute_email_stats')
    emails_sent_this_hour = fields.Integer('Emails Sent This Hour', compute='_compute_email_stats')
    total_emails_sent = fields.Integer('Total Emails Sent', compute='_compute_email_stats')
    last_sent_date = fields.Datetime('Last Sent Date')
    
    # Error Handling
    retry_failed_emails = fields.Boolean('Retry Failed Emails', default=True)
    max_retry_attempts = fields.Integer('Max Retry Attempts', default=3)
    retry_delay_hours = fields.Integer('Retry Delay (Hours)', default=1)
    
    @api.depends('email_log_ids')
    def _compute_email_stats(self):
        for record in self:
            today = fields.Date.today()
            this_hour = fields.Datetime.now().replace(minute=0, second=0, microsecond=0)
            
            logs = record.email_log_ids
            record.total_emails_sent = len(logs.filtered(lambda l: l.state == 'sent'))
            record.emails_sent_today = len(logs.filtered(
                lambda l: l.state == 'sent' and l.sent_date.date() == today
            ))
            record.emails_sent_this_hour = len(logs.filtered(
                lambda l: l.state == 'sent' and l.sent_date >= this_hour
            ))
    
    def test_connection(self):
        """Test SMTP connection"""
        self.ensure_one()
        
        try:
            if self.smtp_encryption == 'ssl':
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                if self.smtp_encryption == 'tls':
                    server.starttls()
            
            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)
            
            server.quit()
            return True, _('SMTP connection successful.')
        
        except Exception as e:
            return False, _('SMTP connection failed: %s') % str(e)
    
    def send_email(self, to_emails, subject, body_html='', body_text='', attachments=None, priority='normal'):
        """Send email using this service"""
        self.ensure_one()
        
        # Check rate limits
        if not self._check_rate_limits():
            raise UserError(_('Email rate limit exceeded. Please try again later.'))
        
        # Prepare email
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{self.from_name or 'Odoo'} <{self.from_email}>"
        msg['To'] = ', '.join(to_emails) if isinstance(to_emails, list) else to_emails
        msg['Subject'] = subject
        
        if self.reply_to:
            msg['Reply-To'] = self.reply_to
        
        # Add body
        if body_text:
            text_part = MIMEText(body_text, 'plain', 'utf-8')
            msg.attach(text_part)
        
        if body_html:
            html_part = MIMEText(body_html, 'html', 'utf-8')
            msg.attach(html_part)
        
        # Add attachments
        if attachments:
            for attachment in attachments:
                self._add_attachment(msg, attachment)
        
        # Send email
        try:
            success = self._send_smtp_email(msg, to_emails)
            
            # Log email
            self._log_email(to_emails, subject, 'sent' if success else 'failed')
            
            if success:
                self.write({'last_sent_date': fields.Datetime.now()})
                return True
            else:
                return False
        
        except Exception as e:
            _logger.error(f"Email sending failed: {str(e)}")
            self._log_email(to_emails, subject, 'failed', str(e))
            return False
    
    def _check_rate_limits(self):
        """Check if rate limits are not exceeded"""
        if self.emails_sent_this_hour >= self.max_emails_per_hour:
            return False
        
        if self.emails_sent_today >= self.max_emails_per_day:
            return False
        
        return True
    
    def _send_smtp_email(self, msg, to_emails):
        """Send email via SMTP"""
        try:
            if self.smtp_encryption == 'ssl':
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                if self.smtp_encryption == 'tls':
                    server.starttls()
            
            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)
            
            # Convert to list if single email
            if isinstance(to_emails, str):
                to_emails = [to_emails]
            
            server.send_message(msg, to_addrs=to_emails)
            server.quit()
            
            return True
        
        except Exception as e:
            _logger.error(f"SMTP error: {str(e)}")
            return False
    
    def _add_attachment(self, msg, attachment):
        """Add attachment to email"""
        try:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.get('content', b''))
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {attachment.get("filename", "attachment")}'
            )
            msg.attach(part)
        except Exception as e:
            _logger.error(f"Failed to add attachment: {str(e)}")
    
    def _log_email(self, to_emails, subject, state, error_message=''):
        """Log email sending attempt"""
        log_values = {
            'service_id': self.id,
            'to_emails': json.dumps(to_emails if isinstance(to_emails, list) else [to_emails]),
            'subject': subject,
            'state': state,
            'error_message': error_message,
            'sent_date': fields.Datetime.now() if state == 'sent' else False,
        }
        
        self.env['email.log'].create(log_values)
    
    def process_failed_emails(self):
        """Process failed emails for retry"""
        if not self.retry_failed_emails:
            return
        
        failed_logs = self.env['email.log'].search([
            ('service_id', '=', self.id),
            ('state', '=', 'failed'),
            ('retry_count', '<', self.max_retry_attempts),
            ('next_retry_date', '<=', fields.Datetime.now())
        ])
        
        for log in failed_logs:
            try:
                # Retry sending email
                success = self.send_email(
                    to_emails=json.loads(log.to_emails),
                    subject=log.subject,
                    body_html=log.body_html,
                    body_text=log.body_text
                )
                
                if success:
                    log.write({
                        'state': 'sent',
                        'sent_date': fields.Datetime.now(),
                        'retry_count': log.retry_count + 1
                    })
                else:
                    log.write({
                        'retry_count': log.retry_count + 1,
                        'next_retry_date': fields.Datetime.now() + timedelta(hours=self.retry_delay_hours)
                    })
            
            except Exception as e:
                _logger.error(f"Retry failed for email log {log.id}: {str(e)}")
                log.write({
                    'retry_count': log.retry_count + 1,
                    'next_retry_date': fields.Datetime.now() + timedelta(hours=self.retry_delay_hours),
                    'error_message': str(e)
                })
    
    @api.model
    def send_notification_email(self, template_id, recipient_data, workflow_data, approver_data=None, approval_data=None):
        """Send notification email using template"""
        template = self.env['notification.template'].browse(template_id)
        if not template.exists():
            raise UserError(_('Notification template not found.'))
        
        # Get default email service
        service = self.search([('active', '=', True)], limit=1)
        if not service:
            raise UserError(_('No active email service configured.'))
        
        # Render template
        rendered = template.render_template(workflow_data, approver_data, approval_data)
        
        # Prepare recipient emails
        to_emails = []
        if isinstance(recipient_data, list):
            for recipient in recipient_data:
                if recipient.get('email'):
                    to_emails.append(recipient['email'])
        elif isinstance(recipient_data, dict) and recipient_data.get('email'):
            to_emails.append(recipient_data['email'])
        
        if not to_emails:
            raise UserError(_('No valid email addresses found in recipient data.'))
        
        # Send email
        return service.send_email(
            to_emails=to_emails,
            subject=rendered['subject'],
            body_html=rendered['body_html'],
            body_text=rendered['body_text']
        )
    
    def action_test_email(self):
        """Send test email"""
        self.ensure_one()
        
        test_email = self.env.user.email
        if not test_email:
            raise UserError(_('User email not configured.'))
        
        success = self.send_email(
            to_emails=[test_email],
            subject='Test Email from Odoo Approval System',
            body_html='<p>This is a test email from the Odoo Approval System.</p>',
            body_text='This is a test email from the Odoo Approval System.'
        )
        
        if success:
            raise UserError(_('Test email sent successfully to %s') % test_email)
        else:
            raise UserError(_('Failed to send test email.'))


class EmailLog(models.Model):
    _name = 'email.log'
    _description = 'Email Log'
    _order = 'create_date desc'

    service_id = fields.Many2one('email.service', string='Email Service', required=True)
    to_emails = fields.Text('To Emails', required=True)
    subject = fields.Char('Subject', required=True)
    body_html = fields.Html('Body (HTML)')
    body_text = fields.Text('Body (Text)')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced')
    ], string='Status', default='draft')
    
    sent_date = fields.Datetime('Sent Date')
    error_message = fields.Text('Error Message')
    
    # Retry Information
    retry_count = fields.Integer('Retry Count', default=0)
    next_retry_date = fields.Datetime('Next Retry Date')
    
    # Tracking
    opened_date = fields.Datetime('Opened Date')
    clicked_date = fields.Datetime('Clicked Date')
    
    def action_retry(self):
        """Retry sending email"""
        self.ensure_one()
        
        if self.state != 'failed':
            raise UserError(_('Only failed emails can be retried.'))
        
        try:
            success = self.service_id.send_email(
                to_emails=json.loads(self.to_emails),
                subject=self.subject,
                body_html=self.body_html,
                body_text=self.body_text
            )
            
            if success:
                self.write({
                    'state': 'sent',
                    'sent_date': fields.Datetime.now(),
                    'retry_count': self.retry_count + 1
                })
            else:
                self.write({
                    'retry_count': self.retry_count + 1,
                    'next_retry_date': fields.Datetime.now() + timedelta(hours=1)
                })
        
        except Exception as e:
            self.write({
                'error_message': str(e),
                'retry_count': self.retry_count + 1,
                'next_retry_date': fields.Datetime.now() + timedelta(hours=1)
            })


class EmailTemplate(models.Model):
    _name = 'email.template'
    _description = 'Email Template for Notifications'
    _inherit = ['mail.template']
    
    # Override attachment_ids to use different relation table
    attachment_ids = fields.Many2many('ir.attachment', 'email_template_attachment_rel', 'template_id', 'attachment_id', string='Attachments')
    
    # Override to add approval-specific fields
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
    ], string='Template Type')
    
    # Approval-specific template variables
    approval_variables = fields.Text('Approval Variables', 
        default='{{workflow.name}}, {{workflow.amount}}, {{workflow.requester}}, {{approver.name}}, {{approval.deadline}}')
    
    def render_template_with_approval_data(self, workflow_data, approver_data=None, approval_data=None):
        """Render template with approval-specific data"""
        template_vars = {
            'workflow': workflow_data,
            'approver': approver_data or {},
            'approval': approval_data or {},
            'company': self.env.company,
            'user': self.env.user,
            'date': fields.Datetime.now(),
        }
        
        # Render subject
        subject = self._render_template(self.subject, template_vars)
        
        # Render body
        body_html = self._render_template(self.body_html, template_vars) if self.body_html else ''
        body_text = self._render_template(self.body_text, template_vars) if self.body_text else ''
        
        return {
            'subject': subject,
            'body_html': body_html,
            'body_text': body_text,
        }
    
    def _render_template(self, template_text, variables):
        """Render template text with variables"""
        if not template_text:
            return ''
        
        rendered = template_text
        for key, value in variables.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    placeholder = f'{{{{{key}.{sub_key}}}}}'
                    rendered = rendered.replace(placeholder, str(sub_value or ''))
            else:
                placeholder = f'{{{{{key}}}}}'
                rendered = rendered.replace(placeholder, str(value or ''))
        
        return rendered
