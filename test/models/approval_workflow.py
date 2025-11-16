# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import json
from datetime import datetime, timedelta


class ApprovalWorkflow(models.Model):
    _name = 'approval.workflow'
    _description = 'Approval Workflow Engine'
    _order = 'create_date desc'
    _rec_name = 'name'

    name = fields.Char('Workflow Name', required=True)
    description = fields.Text('Description')
    
    # Workflow Configuration
    workflow_type = fields.Selection([
        ('purchase', 'Purchase Order'),
        ('expense', 'Expense Report'),
        ('leave', 'Leave Request'),
        ('travel', 'Travel Request'),
        ('contract', 'Contract Approval'),
        ('custom', 'Custom Workflow')
    ], string='Workflow Type', required=True)
    
    # Request Information
    requester_id = fields.Many2one('res.users', string='Requester', required=True, default=lambda self: self.env.user)
    requester_dynamic_id = fields.Many2one('dynamic.user', string='Dynamic Requester')
    department_id = fields.Many2one('hr.department', string='Department')
    category_id = fields.Many2one('product.category', string='Category')
    
    # Amount and Details
    amount = fields.Float('Amount', required=True, default=0.0)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    description_detail = fields.Text('Detailed Description')
    
    # Matrix and Levels
    matrix_id = fields.Many2one('multi.matrix', string='Approval Matrix')
    current_level_id = fields.Many2one('multi.matrix.level', string='Current Level')
    total_levels = fields.Integer('Total Levels', compute='_compute_level_info')
    current_level_sequence = fields.Integer('Current Level Sequence', compute='_compute_level_info')
    
    # Approval Process
    approval_ids = fields.One2many('approval.workflow.approval', 'workflow_id', string='Approvals')
    approval_count = fields.Integer('Approval Count', compute='_compute_approval_stats')
    approved_count = fields.Integer('Approved Count', compute='_compute_approval_stats')
    rejected_count = fields.Integer('Rejected Count', compute='_compute_approval_stats')
    pending_count = fields.Integer('Pending Count', compute='_compute_approval_stats')
    
    # Status and State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('escalated', 'Escalated'),
        ('timeout', 'Timeout')
    ], string='Status', default='draft', required=True)
    
    # Dates and Timing
    request_date = fields.Datetime('Request Date', default=fields.Datetime.now)
    approval_deadline = fields.Datetime('Approval Deadline')
    approved_date = fields.Datetime('Approved Date')
    rejected_date = fields.Datetime('Rejected Date')
    cancelled_date = fields.Datetime('Cancelled Date')
    
    # Timeout and Escalation
    timeout_hours = fields.Integer('Timeout Hours', default=0)
    escalation_enabled = fields.Boolean('Escalation Enabled', default=True)
    escalation_user_ids = fields.Many2many('res.users', 'approval_workflow_escalation_rel', 'workflow_id', 'user_id', string='Escalation Users')
    
    # Custom Data
    custom_data = fields.Text('Custom Data', help='JSON format for custom workflow data')
    attachment_ids = fields.Many2many('ir.attachment', 'approval_workflow_attachment_rel', 'workflow_id', 'attachment_id', string='Attachments')
    
    # Related Records
    related_model = fields.Char('Related Model')
    related_record_id = fields.Integer('Related Record ID')
    
    # Statistics
    total_processing_time = fields.Float('Total Processing Time (Hours)', compute='_compute_processing_time')
    average_approval_time = fields.Float('Average Approval Time (Hours)', compute='_compute_processing_time')
    
    @api.depends('matrix_id', 'current_level_id')
    def _compute_level_info(self):
        for record in self:
            if record.matrix_id:
                record.total_levels = len(record.matrix_id.approval_levels)
                if record.current_level_id:
                    record.current_level_sequence = record.current_level_id.level_sequence
                else:
                    record.current_level_sequence = 0
            else:
                record.total_levels = 0
                record.current_level_sequence = 0
    
    @api.depends('approval_ids')
    def _compute_approval_stats(self):
        for record in self:
            record.approval_count = len(record.approval_ids)
            record.approved_count = len(record.approval_ids.filtered(lambda a: a.state == 'approved'))
            record.rejected_count = len(record.approval_ids.filtered(lambda a: a.state == 'rejected'))
            record.pending_count = len(record.approval_ids.filtered(lambda a: a.state == 'pending'))
    
    @api.depends('request_date', 'approved_date', 'rejected_date', 'cancelled_date')
    def _compute_processing_time(self):
        for record in self:
            if record.approved_date or record.rejected_date or record.cancelled_date:
                end_date = record.approved_date or record.rejected_date or record.cancelled_date
                if record.request_date and end_date:
                    time_diff = (end_date - record.request_date).total_seconds() / 3600
                    record.total_processing_time = time_diff
                    
                    # Calculate average approval time
                    approved_approvals = record.approval_ids.filtered(lambda a: a.state == 'approved' and a.approved_date)
                    if approved_approvals:
                        total_approval_time = sum([
                            (a.approved_date - a.create_date).total_seconds() / 3600
                            for a in approved_approvals
                        ])
                        record.average_approval_time = total_approval_time / len(approved_approvals)
                    else:
                        record.average_approval_time = 0.0
                else:
                    record.total_processing_time = 0.0
                    record.average_approval_time = 0.0
            else:
                record.total_processing_time = 0.0
                record.average_approval_time = 0.0
    
    @api.constrains('amount')
    def _check_amount(self):
        for record in self:
            if record.amount < 0:
                raise ValidationError(_('Amount cannot be negative.'))
    
    def action_submit(self):
        """Submit workflow for approval"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_('Only draft workflows can be submitted.'))
        
        # Find applicable matrix
        matrix = self._find_applicable_matrix()
        if not matrix:
            raise UserError(_('No applicable approval matrix found for this workflow.'))
        
        # Validate matrix conditions
        is_valid, message = matrix.validate_approval_conditions({
            'amount': self.amount,
            'department_id': self.department_id.id if self.department_id else None,
            'category_id': self.category_id.id if self.category_id else None,
        })
        
        if not is_valid:
            raise UserError(message)
        
        # Set matrix and start approval process
        self.write({
            'matrix_id': matrix.id,
            'current_level_id': matrix.approval_levels[0].id if matrix.approval_levels else False,
            'state': 'pending',
            'approval_deadline': self._calculate_deadline()
        })
        
        # Create initial approvals
        self._create_approvals()
        
        # Send notifications
        self._send_notifications('approval_request')
        
        return True
    
    def _find_applicable_matrix(self):
        """Find applicable approval matrix"""
        return self.env['multi.matrix'].get_applicable_matrix(
            amount=self.amount,
            department_id=self.department_id.id if self.department_id else None,
            category_id=self.category_id.id if self.category_id else None,
            custom_data=self.custom_data
        )
    
    def _calculate_deadline(self):
        """Calculate approval deadline"""
        if self.timeout_hours > 0:
            return fields.Datetime.now() + timedelta(hours=self.timeout_hours)
        elif self.current_level_id and self.current_level_id.timeout_hours > 0:
            return fields.Datetime.now() + timedelta(hours=self.current_level_id.timeout_hours)
        return False
    
    def _create_approvals(self):
        """Create approval records for current level"""
        if not self.current_level_id:
            return
        
        level = self.current_level_id
        approvers = level.get_available_approvers({
            'amount': self.amount,
            'department_id': self.department_id.id if self.department_id else None,
            'category_id': self.category_id.id if self.category_id else None,
        })
        
        for approver in approvers:
            # Check if user can approve this amount
            if not approver.can_approve_amount(self.amount):
                continue
            
            # Check for delegation
            actual_approver = approver
            if not approver.is_available_now():
                delegated_user = approver.get_delegation_user({
                    'amount': self.amount,
                    'department_id': self.department_id.id if self.department_id else None,
                    'category_id': self.category_id.id if self.category_id else None,
                })
                if delegated_user:
                    actual_approver = delegated_user
            
            approval_values = {
                'workflow_id': self.id,
                'level_id': level.id,
                'approver_id': approver.id,
                'delegated_to_id': actual_approver.id if actual_approver != approver else False,
                'state': 'pending',
                'deadline': self.approval_deadline,
            }
            
            self.env['approval.workflow.approval'].create(approval_values)
    
    def _send_notifications(self, notification_type):
        """Send notifications for workflow"""
        # Find applicable notification templates
        templates = self.env['notification.template'].search([
            ('template_type', '=', notification_type),
            ('active', '=', True)
        ])
        
        for template in templates:
            if template.check_conditions({
                'amount': self.amount,
                'department_id': self.department_id.id if self.department_id else None,
                'category_id': self.category_id.id if self.category_id else None,
            }):
                self._queue_notification(template)
    
    def _queue_notification(self, template):
        """Queue notification for sending"""
        # Prepare recipient data
        recipients = self._get_notification_recipients(template)
        
        for recipient in recipients:
            # Render template
            rendered = template.render_template(
                workflow_data=self._get_workflow_data(),
                approver_data=recipient.get('approver_data', {}),
                approval_data=recipient.get('approval_data', {})
            )
            
            # Calculate send time
            send_time = fields.Datetime.now()
            if not template.send_immediately:
                if template.delay_hours > 0:
                    send_time += timedelta(hours=template.delay_hours)
                elif template.send_time:
                    # Parse send time and schedule for today/tomorrow
                    try:
                        send_hour, send_minute = map(int, template.send_time.split(':'))
                        today = fields.Datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                        scheduled_time = today.replace(hour=send_hour, minute=send_minute)
                        if scheduled_time <= fields.Datetime.now():
                            scheduled_time += timedelta(days=1)
                        send_time = scheduled_time
                    except ValueError:
                        pass
            
            # Queue notification
            queue_values = {
                'template_id': template.id,
                'workflow_id': self.id,
                'scheduled_date': send_time,
                'recipient_data': json.dumps(recipient),
                'message_data': json.dumps(rendered),
            }
            
            self.env['notification.queue'].create(queue_values)
    
    def _get_notification_recipients(self, template):
        """Get notification recipients based on template configuration"""
        recipients = []
        
        if template.recipient_type == 'approver':
            for approval in self.approval_ids.filtered(lambda a: a.state == 'pending'):
                approver_data = {
                    'id': approval.approver_id.id,
                    'name': approval.approver_id.name,
                    'email': approval.approver_id.user_id.email if approval.approver_id.user_id else '',
                }
                recipients.append({
                    'type': 'email',
                    'email': approver_data['email'],
                    'user_id': approval.approver_id.user_id.id if approval.approver_id.user_id else False,
                    'approver_data': approver_data,
                    'approval_data': {
                        'id': approval.id,
                        'deadline': approval.deadline,
                        'level': approval.level_id.name,
                    }
                })
        
        elif template.recipient_type == 'requester':
            recipients.append({
                'type': 'email',
                'email': self.requester_id.email,
                'user_id': self.requester_id.id,
                'approver_data': {
                    'id': self.requester_id.id,
                    'name': self.requester_id.name,
                    'email': self.requester_id.email,
                }
            })
        
        elif template.recipient_type == 'custom' and template.custom_recipients:
            try:
                custom_recipients = json.loads(template.custom_recipients)
                recipients.extend(custom_recipients)
            except (json.JSONDecodeError, KeyError):
                pass
        
        return recipients
    
    def _get_workflow_data(self):
        """Get workflow data for template rendering"""
        return {
            'id': self.id,
            'name': self.name,
            'amount': self.amount,
            'currency': self.currency_id.name,
            'requester': self.requester_id.name,
            'department': self.department_id.name if self.department_id else '',
            'category': self.category_id.name if self.category_id else '',
            'description': self.description,
            'request_date': self.request_date,
            'deadline': self.approval_deadline,
            'state': self.state,
        }
    
    def action_approve(self, approver_id, comments=''):
        """Approve workflow by specific approver"""
        self.ensure_one()
        
        approval = self.approval_ids.filtered(
            lambda a: a.approver_id.id == approver_id and a.state == 'pending'
        )
        
        if not approval:
            raise UserError(_('No pending approval found for this approver.'))
        
        approval.write({
            'state': 'approved',
            'approved_date': fields.Datetime.now(),
            'comments': comments,
        })
        
        # Check if current level is complete
        if self._is_current_level_complete():
            self._move_to_next_level()
        else:
            # Send reminder notifications
            self._send_notifications('approval_reminder')
    
    def action_reject(self, approver_id, comments=''):
        """Reject workflow by specific approver"""
        self.ensure_one()
        
        approval = self.approval_ids.filtered(
            lambda a: a.approver_id.id == approver_id and a.state == 'pending'
        )
        
        if not approval:
            raise UserError(_('No pending approval found for this approver.'))
        
        approval.write({
            'state': 'rejected',
            'rejected_date': fields.Datetime.now(),
            'comments': comments,
        })
        
        # Reject entire workflow
        self.write({
            'state': 'rejected',
            'rejected_date': fields.Datetime.now(),
        })
        
        # Send rejection notifications
        self._send_notifications('approval_rejected')
    
    def _is_current_level_complete(self):
        """Check if current level is complete"""
        if not self.current_level_id:
            return True
        
        level = self.current_level_id
        level_approvals = self.approval_ids.filtered(lambda a: a.level_id == level)
        
        if level.approval_type == 'single':
            return any(level_approvals.filtered(lambda a: a.state == 'approved'))
        elif level.approval_type == 'all':
            return all(level_approvals.filtered(lambda a: a.state == 'approved'))
        elif level.approval_type == 'any':
            return any(level_approvals.filtered(lambda a: a.state == 'approved'))
        elif level.approval_type == 'multiple':
            approved_count = len(level_approvals.filtered(lambda a: a.state == 'approved'))
            return approved_count >= level.required_approvals
        
        return False
    
    def _move_to_next_level(self):
        """Move to next approval level"""
        if not self.matrix_id:
            return
        
        current_sequence = self.current_level_sequence
        next_level = self.matrix_id.approval_levels.filtered(
            lambda l: l.level_sequence > current_sequence
        ).sorted('level_sequence')
        
        if next_level:
            # Move to next level
            self.write({
                'current_level_id': next_level[0].id,
                'approval_deadline': self._calculate_deadline()
            })
            
            # Create approvals for next level
            self._create_approvals()
            
            # Send notifications
            self._send_notifications('approval_request')
        else:
            # All levels completed
            self.write({
                'state': 'approved',
                'approved_date': fields.Datetime.now(),
                'current_level_id': False,
            })
            
            # Send completion notifications
            self._send_notifications('workflow_completed')
    
    def action_cancel(self):
        """Cancel workflow"""
        self.ensure_one()
        
        if self.state in ['approved', 'rejected', 'cancelled']:
            raise UserError(_('Cannot cancel workflow in current state.'))
        
        self.write({
            'state': 'cancelled',
            'cancelled_date': fields.Datetime.now(),
        })
        
        # Cancel pending approvals
        self.approval_ids.filtered(lambda a: a.state == 'pending').write({
            'state': 'cancelled',
            'cancelled_date': fields.Datetime.now(),
        })
        
        # Send cancellation notifications
        self._send_notifications('workflow_cancelled')
    
    def action_escalate(self):
        """Escalate workflow"""
        self.ensure_one()
        
        if not self.escalation_enabled or not self.escalation_user_ids:
            raise UserError(_('Escalation is not configured for this workflow.'))
        
        self.write({'state': 'escalated'})
        
        # Send escalation notifications
        self._send_notifications('approval_escalated')
    
    @api.model
    def process_timeouts(self):
        """Process timed out workflows"""
        timeout_workflows = self.search([
            ('state', '=', 'pending'),
            ('approval_deadline', '!=', False),
            ('approval_deadline', '<', fields.Datetime.now())
        ])
        
        for workflow in timeout_workflows:
            # Check if current level has auto-approve on timeout
            if (workflow.current_level_id and 
                workflow.current_level_id.auto_approve):
                # Auto approve current level
                workflow._move_to_next_level()
            else:
                # Mark as timeout
                workflow.write({'state': 'timeout'})
                workflow._send_notifications('approval_timeout')


class ApprovalWorkflowApproval(models.Model):
    _name = 'approval.workflow.approval'
    _description = 'Individual Approval in Workflow'
    _order = 'create_date'

    workflow_id = fields.Many2one('approval.workflow', string='Workflow', required=True, ondelete='cascade')
    level_id = fields.Many2one('multi.matrix.level', string='Approval Level', required=True)
    approver_id = fields.Many2one('dynamic.user', string='Approver', required=True)
    delegated_to_id = fields.Many2one('dynamic.user', string='Delegated To')
    
    # Approval Details
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('timeout', 'Timeout')
    ], string='Status', default='pending', required=True)
    
    # Dates
    create_date = fields.Datetime('Created Date', default=fields.Datetime.now)
    approved_date = fields.Datetime('Approved Date')
    rejected_date = fields.Datetime('Rejected Date')
    cancelled_date = fields.Datetime('Cancelled Date')
    deadline = fields.Datetime('Deadline')
    
    # Comments and Notes
    comments = fields.Text('Comments')
    rejection_reason = fields.Text('Rejection Reason')
    
    # Processing Time
    processing_time = fields.Float('Processing Time (Hours)', compute='_compute_processing_time')
    
    @api.depends('create_date', 'approved_date', 'rejected_date', 'cancelled_date')
    def _compute_processing_time(self):
        for record in self:
            if record.approved_date or record.rejected_date or record.cancelled_date:
                end_date = record.approved_date or record.rejected_date or record.cancelled_date
                if record.create_date and end_date:
                    time_diff = (end_date - record.create_date).total_seconds() / 3600
                    record.processing_time = time_diff
                else:
                    record.processing_time = 0.0
            else:
                record.processing_time = 0.0
    
    def action_approve(self, comments=''):
        """Approve this approval"""
        self.ensure_one()
        
        if self.state != 'pending':
            raise UserError(_('Only pending approvals can be approved.'))
        
        self.write({
            'state': 'approved',
            'approved_date': fields.Datetime.now(),
            'comments': comments,
        })
        
        # Check if workflow can move to next level
        if self.workflow_id._is_current_level_complete():
            self.workflow_id._move_to_next_level()
    
    def action_reject(self, reason=''):
        """Reject this approval"""
        self.ensure_one()
        
        if self.state != 'pending':
            raise UserError(_('Only pending approvals can be rejected.'))
        
        self.write({
            'state': 'rejected',
            'rejected_date': fields.Datetime.now(),
            'rejection_reason': reason,
        })
        
        # Reject entire workflow
        self.workflow_id.write({
            'state': 'rejected',
            'rejected_date': fields.Datetime.now(),
        })
    
    def action_cancel(self):
        """Cancel this approval"""
        self.ensure_one()
        
        if self.state not in ['pending']:
            raise UserError(_('Only pending approvals can be cancelled.'))
        
        self.write({
            'state': 'cancelled',
            'cancelled_date': fields.Datetime.now(),
        })
