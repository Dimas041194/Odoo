# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime, timedelta

from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class ApprovalAPIController(http.Controller):
    
    @http.route('/api/approval/workflows', type='http', auth='user', methods=['GET'], csrf=False)
    def get_workflows(self, **kwargs):
        """Get approval workflows with filtering and pagination"""
        try:
            # Parse parameters
            page = int(kwargs.get('page', 1))
            limit = int(kwargs.get('limit', 20))
            state = kwargs.get('state')
            workflow_type = kwargs.get('workflow_type')
            requester_id = kwargs.get('requester_id')
            department_id = kwargs.get('department_id')
            search = kwargs.get('search')
            
            # Build domain
            domain = []
            if state:
                domain.append(('state', '=', state))
            if workflow_type:
                domain.append(('workflow_type', '=', workflow_type))
            if requester_id:
                domain.append(('requester_id', '=', int(requester_id)))
            if department_id:
                domain.append(('department_id', '=', int(department_id)))
            if search:
                domain.append('|')
                domain.append(('name', 'ilike', search))
                domain.append(('description', 'ilike', search))
            
            # Get workflows
            workflows = request.env['approval.workflow'].search(domain, limit=limit, offset=(page-1)*limit)
            total_count = request.env['approval.workflow'].search_count(domain)
            
            # Prepare response data
            workflow_data = []
            for workflow in workflows:
                workflow_data.append({
                    'id': workflow.id,
                    'name': workflow.name,
                    'description': workflow.description,
                    'workflow_type': workflow.workflow_type,
                    'state': workflow.state,
                    'amount': workflow.amount,
                    'currency': workflow.currency_id.name,
                    'requester': {
                        'id': workflow.requester_id.id,
                        'name': workflow.requester_id.name,
                        'email': workflow.requester_id.email,
                    },
                    'department': {
                        'id': workflow.department_id.id,
                        'name': workflow.department_id.name,
                    } if workflow.department_id else None,
                    'category': {
                        'id': workflow.category_id.id,
                        'name': workflow.category_id.name,
                    } if workflow.category_id else None,
                    'request_date': workflow.request_date.isoformat() if workflow.request_date else None,
                    'approval_deadline': workflow.approval_deadline.isoformat() if workflow.approval_deadline else None,
                    'approved_date': workflow.approved_date.isoformat() if workflow.approved_date else None,
                    'current_level': {
                        'id': workflow.current_level_id.id,
                        'name': workflow.current_level_id.name,
                        'sequence': workflow.current_level_sequence,
                    } if workflow.current_level_id else None,
                    'total_levels': workflow.total_levels,
                    'approval_stats': {
                        'total': workflow.approval_count,
                        'approved': workflow.approved_count,
                        'rejected': workflow.rejected_count,
                        'pending': workflow.pending_count,
                    },
                    'processing_time': workflow.total_processing_time,
                })
            
            return request.make_json_response({
                'success': True,
                'data': workflow_data,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total_count,
                    'pages': (total_count + limit - 1) // limit,
                }
            })
        
        except Exception as e:
            _logger.error(f"Error getting workflows: {str(e)}")
            return request.make_json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    @http.route('/api/approval/workflows', type='http', auth='user', methods=['POST'], csrf=False)
    def create_workflow(self, **kwargs):
        """Create new approval workflow"""
        try:
            # Parse request data
            data = json.loads(request.httprequest.data.decode('utf-8'))
            
            # Validate required fields
            required_fields = ['name', 'workflow_type', 'amount']
            for field in required_fields:
                if field not in data:
                    return request.make_json_response({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }, status=400)
            
            # Create workflow
            workflow_values = {
                'name': data['name'],
                'description': data.get('description', ''),
                'workflow_type': data['workflow_type'],
                'amount': float(data['amount']),
                'currency_id': data.get('currency_id'),
                'department_id': data.get('department_id'),
                'category_id': data.get('category_id'),
                'description_detail': data.get('description_detail', ''),
                'custom_data': json.dumps(data.get('custom_data', {})) if data.get('custom_data') else False,
            }
            
            workflow = request.env['approval.workflow'].create(workflow_values)
            
            # Submit workflow if requested
            if data.get('submit', False):
                workflow.action_submit()
            
            return request.make_json_response({
                'success': True,
                'data': {
                    'id': workflow.id,
                    'name': workflow.name,
                    'state': workflow.state,
                }
            })
        
        except Exception as e:
            _logger.error(f"Error creating workflow: {str(e)}")
            return request.make_json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    @http.route('/api/approval/workflows/<int:workflow_id>', type='http', auth='user', methods=['GET'], csrf=False)
    def get_workflow(self, workflow_id, **kwargs):
        """Get specific workflow details"""
        try:
            workflow = request.env['approval.workflow'].browse(workflow_id)
            if not workflow.exists():
                return request.make_json_response({
                    'success': False,
                    'error': 'Workflow not found'
                }, status=404)
            
            # Get approval details
            approvals = []
            for approval in workflow.approval_ids:
                approvals.append({
                    'id': approval.id,
                    'level': {
                        'id': approval.level_id.id,
                        'name': approval.level_id.name,
                        'sequence': approval.level_id.level_sequence,
                    },
                    'approver': {
                        'id': approval.approver_id.id,
                        'name': approval.approver_id.name,
                        'email': approval.approver_id.user_id.email if approval.approver_id.user_id else None,
                    },
                    'delegated_to': {
                        'id': approval.delegated_to_id.id,
                        'name': approval.delegated_to_id.name,
                        'email': approval.delegated_to_id.user_id.email if approval.delegated_to_id.user_id else None,
                    } if approval.delegated_to_id else None,
                    'state': approval.state,
                    'comments': approval.comments,
                    'rejection_reason': approval.rejection_reason,
                    'create_date': approval.create_date.isoformat(),
                    'approved_date': approval.approved_date.isoformat() if approval.approved_date else None,
                    'rejected_date': approval.rejected_date.isoformat() if approval.rejected_date else None,
                    'deadline': approval.deadline.isoformat() if approval.deadline else None,
                    'processing_time': approval.processing_time,
                })
            
            workflow_data = {
                'id': workflow.id,
                'name': workflow.name,
                'description': workflow.description,
                'workflow_type': workflow.workflow_type,
                'state': workflow.state,
                'amount': workflow.amount,
                'currency': workflow.currency_id.name,
                'requester': {
                    'id': workflow.requester_id.id,
                    'name': workflow.requester_id.name,
                    'email': workflow.requester_id.email,
                },
                'department': {
                    'id': workflow.department_id.id,
                    'name': workflow.department_id.name,
                } if workflow.department_id else None,
                'category': {
                    'id': workflow.category_id.id,
                    'name': workflow.category_id.name,
                } if workflow.category_id else None,
                'request_date': workflow.request_date.isoformat() if workflow.request_date else None,
                'approval_deadline': workflow.approval_deadline.isoformat() if workflow.approval_deadline else None,
                'approved_date': workflow.approved_date.isoformat() if workflow.approved_date else None,
                'rejected_date': workflow.rejected_date.isoformat() if workflow.rejected_date else None,
                'cancelled_date': workflow.cancelled_date.isoformat() if workflow.cancelled_date else None,
                'matrix': {
                    'id': workflow.matrix_id.id,
                    'name': workflow.matrix_id.name,
                } if workflow.matrix_id else None,
                'current_level': {
                    'id': workflow.current_level_id.id,
                    'name': workflow.current_level_id.name,
                    'sequence': workflow.current_level_sequence,
                } if workflow.current_level_id else None,
                'total_levels': workflow.total_levels,
                'approvals': approvals,
                'attachments': [
                    {
                        'id': att.id,
                        'name': att.name,
                        'url': f'/web/content/{att.id}?download=true',
                    } for att in workflow.attachment_ids
                ],
                'custom_data': json.loads(workflow.custom_data) if workflow.custom_data else {},
                'processing_time': workflow.total_processing_time,
                'average_approval_time': workflow.average_approval_time,
            }
            
            return request.make_json_response({
                'success': True,
                'data': workflow_data
            })
        
        except Exception as e:
            _logger.error(f"Error getting workflow: {str(e)}")
            return request.make_json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    @http.route('/api/approval/workflows/<int:workflow_id>/approve', type='http', auth='user', methods=['POST'], csrf=False)
    def approve_workflow(self, workflow_id, **kwargs):
        """Approve workflow"""
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
            comments = data.get('comments', '')
            
            workflow = request.env['approval.workflow'].browse(workflow_id)
            if not workflow.exists():
                return request.make_json_response({
                    'success': False,
                    'error': 'Workflow not found'
                }, status=404)
            
            # Check if user can approve
            current_user_id = request.env.user.id
            can_approve = any(
                approval.approver_id.user_id.id == current_user_id and approval.state == 'pending'
                for approval in workflow.approval_ids
            )
            
            if not can_approve:
                return request.make_json_response({
                    'success': False,
                    'error': 'You are not authorized to approve this workflow'
                }, status=403)
            
            # Approve workflow
            workflow.action_approve(current_user_id, comments)
            
            return request.make_json_response({
                'success': True,
                'message': 'Workflow approved successfully'
            })
        
        except Exception as e:
            _logger.error(f"Error approving workflow: {str(e)}")
            return request.make_json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    @http.route('/api/approval/workflows/<int:workflow_id>/reject', type='http', auth='user', methods=['POST'], csrf=False)
    def reject_workflow(self, workflow_id, **kwargs):
        """Reject workflow"""
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
            reason = data.get('reason', '')
            
            workflow = request.env['approval.workflow'].browse(workflow_id)
            if not workflow.exists():
                return request.make_json_response({
                    'success': False,
                    'error': 'Workflow not found'
                }, status=404)
            
            # Check if user can reject
            current_user_id = request.env.user.id
            can_reject = any(
                approval.approver_id.user_id.id == current_user_id and approval.state == 'pending'
                for approval in workflow.approval_ids
            )
            
            if not can_reject:
                return request.make_json_response({
                    'success': False,
                    'error': 'You are not authorized to reject this workflow'
                }, status=403)
            
            # Reject workflow
            workflow.action_reject(current_user_id, reason)
            
            return request.make_json_response({
                'success': True,
                'message': 'Workflow rejected successfully'
            })
        
        except Exception as e:
            _logger.error(f"Error rejecting workflow: {str(e)}")
            return request.make_json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    @http.route('/api/approval/workflows/<int:workflow_id>/cancel', type='http', auth='user', methods=['POST'], csrf=False)
    def cancel_workflow(self, workflow_id, **kwargs):
        """Cancel workflow"""
        try:
            workflow = request.env['approval.workflow'].browse(workflow_id)
            if not workflow.exists():
                return request.make_json_response({
                    'success': False,
                    'error': 'Workflow not found'
                }, status=404)
            
            # Check if user can cancel
            if workflow.requester_id.id != request.env.user.id:
                return request.make_json_response({
                    'success': False,
                    'error': 'Only the requester can cancel this workflow'
                }, status=403)
            
            # Cancel workflow
            workflow.action_cancel()
            
            return request.make_json_response({
                'success': True,
                'message': 'Workflow cancelled successfully'
            })
        
        except Exception as e:
            _logger.error(f"Error cancelling workflow: {str(e)}")
            return request.make_json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    @http.route('/api/approval/matrices', type='http', auth='user', methods=['GET'], csrf=False)
    def get_matrices(self, **kwargs):
        """Get approval matrices"""
        try:
            matrices = request.env['multi.matrix'].search([('active', '=', True)])
            
            matrix_data = []
            for matrix in matrices:
                matrix_data.append({
                    'id': matrix.id,
                    'name': matrix.name,
                    'description': matrix.description,
                    'matrix_type': matrix.matrix_type,
                    'min_amount': matrix.min_amount,
                    'max_amount': matrix.max_amount,
                    'currency': matrix.currency_id.name,
                    'level_count': matrix.level_count,
                    'departments': [
                        {'id': dept.id, 'name': dept.name}
                        for dept in matrix.department_ids
                    ],
                    'categories': [
                        {'id': cat.id, 'name': cat.name}
                        for cat in matrix.category_ids
                    ],
                })
            
            return request.make_json_response({
                'success': True,
                'data': matrix_data
            })
        
        except Exception as e:
            _logger.error(f"Error getting matrices: {str(e)}")
            return request.make_json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    @http.route('/api/approval/users', type='http', auth='user', methods=['GET'], csrf=False)
    def get_approvers(self, **kwargs):
        """Get available approvers"""
        try:
            criteria = {}
            if kwargs.get('amount'):
                criteria['amount'] = float(kwargs['amount'])
            if kwargs.get('department_id'):
                criteria['department_id'] = int(kwargs['department_id'])
            if kwargs.get('category_id'):
                criteria['category_id'] = int(kwargs['category_id'])
            
            approvers = request.env['dynamic.user'].get_available_approvers(criteria)
            
            approver_data = []
            for approver in approvers:
                approver_data.append({
                    'id': approver.id,
                    'name': approver.name,
                    'user': {
                        'id': approver.user_id.id,
                        'name': approver.user_id.name,
                        'email': approver.user_id.email,
                    },
                    'department': {
                        'id': approver.department_id.id,
                        'name': approver.department_id.name,
                    } if approver.department_id else None,
                    'job': {
                        'id': approver.job_id.id,
                        'name': approver.job_id.name,
                    } if approver.job_id else None,
                    'approval_capacity': approver.approval_capacity,
                    'max_approval_amount': approver.max_approval_amount,
                    'currency': approver.currency_id.name,
                    'current_status': approver.current_status,
                    'is_online': approver.is_online,
                    'last_activity': approver.last_activity.isoformat() if approver.last_activity else None,
                })
            
            return request.make_json_response({
                'success': True,
                'data': approver_data
            })
        
        except Exception as e:
            _logger.error(f"Error getting approvers: {str(e)}")
            return request.make_json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    @http.route('/api/approval/notifications', type='http', auth='user', methods=['GET'], csrf=False)
    def get_notifications(self, **kwargs):
        """Get user notifications"""
        try:
            page = int(kwargs.get('page', 1))
            limit = int(kwargs.get('limit', 20))
            state = kwargs.get('state')
            
            domain = [('recipient_user_id', '=', request.env.user.id)]
            if state:
                domain.append(('state', '=', state))
            
            notifications = request.env['notification.log'].search(domain, limit=limit, offset=(page-1)*limit)
            total_count = request.env['notification.log'].search_count(domain)
            
            notification_data = []
            for notification in notifications:
                notification_data.append({
                    'id': notification.id,
                    'subject': notification.subject,
                    'body_html': notification.body_html,
                    'body_text': notification.body_text,
                    'state': notification.state,
                    'recipient_type': notification.recipient_type,
                    'sent_date': notification.sent_date.isoformat() if notification.sent_date else None,
                    'opened_date': notification.opened_date.isoformat() if notification.opened_date else None,
                    'clicked_date': notification.clicked_date.isoformat() if notification.clicked_date else None,
                    'workflow': {
                        'id': notification.workflow_id.id,
                        'name': notification.workflow_id.name,
                    } if notification.workflow_id else None,
                })
            
            return request.make_json_response({
                'success': True,
                'data': notification_data,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total_count,
                    'pages': (total_count + limit - 1) // limit,
                }
            })
        
        except Exception as e:
            _logger.error(f"Error getting notifications: {str(e)}")
            return request.make_json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    @http.route('/api/approval/notifications/<int:notification_id>/mark_opened', type='http', auth='user', methods=['POST'], csrf=False)
    def mark_notification_opened(self, notification_id, **kwargs):
        """Mark notification as opened"""
        try:
            notification = request.env['notification.log'].browse(notification_id)
            if not notification.exists():
                return request.make_json_response({
                    'success': False,
                    'error': 'Notification not found'
                }, status=404)
            
            if notification.recipient_user_id.id != request.env.user.id:
                return request.make_json_response({
                    'success': False,
                    'error': 'Not authorized to mark this notification'
                }, status=403)
            
            notification.action_mark_opened()
            
            return request.make_json_response({
                'success': True,
                'message': 'Notification marked as opened'
            })
        
        except Exception as e:
            _logger.error(f"Error marking notification opened: {str(e)}")
            return request.make_json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    @http.route('/api/approval/dashboard', type='http', auth='user', methods=['GET'], csrf=False)
    def get_dashboard_data(self, **kwargs):
        """Get dashboard data for current user"""
        try:
            user = request.env.user
            
            # Get user's workflows
            my_workflows = request.env['approval.workflow'].search([
                ('requester_id', '=', user.id)
            ])
            
            # Get pending approvals for user
            pending_approvals = request.env['approval.workflow.approval'].search([
                ('approver_id.user_id', '=', user.id),
                ('state', '=', 'pending')
            ])
            
            # Get statistics
            stats = {
                'my_workflows': {
                    'total': len(my_workflows),
                    'pending': len(my_workflows.filtered(lambda w: w.state == 'pending')),
                    'approved': len(my_workflows.filtered(lambda w: w.state == 'approved')),
                    'rejected': len(my_workflows.filtered(lambda w: w.state == 'rejected')),
                },
                'pending_approvals': {
                    'total': len(pending_approvals),
                    'overdue': len(pending_approvals.filtered(
                        lambda a: a.deadline and a.deadline < fields.Datetime.now()
                    )),
                },
                'recent_activities': []
            }
            
            # Get recent activities
            recent_workflows = my_workflows.sorted('write_date', reverse=True)[:5]
            for workflow in recent_workflows:
                stats['recent_activities'].append({
                    'id': workflow.id,
                    'name': workflow.name,
                    'state': workflow.state,
                    'amount': workflow.amount,
                    'currency': workflow.currency_id.name,
                    'last_update': workflow.write_date.isoformat(),
                })
            
            return request.make_json_response({
                'success': True,
                'data': stats
            })
        
        except Exception as e:
            _logger.error(f"Error getting dashboard data: {str(e)}")
            return request.make_json_response({
                'success': False,
                'error': str(e)
            }, status=500)
