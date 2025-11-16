# Advanced Approval Workflow System for Odoo 18 Community Edition

## Overview

This module provides a comprehensive approval workflow system for Odoo 18 Community Edition with advanced features including multi-matrix approval, dynamic user management, and email notifications.

## Features

### 🎯 Multi-Matrix Approval System
- **Multiple Approval Matrices**: Create different approval matrices for various business processes
- **Flexible Approval Types**: Amount-based, department-based, category-based, and custom approval rules
- **Hybrid Matrices**: Combine multiple criteria for complex approval scenarios
- **Approval Levels**: Multiple approval levels with different approval types (single, multiple, any, all, percentage, quorum)

### 👥 Dynamic User Management
- **Real-time Availability**: Track user availability and status in real-time
- **Delegation Support**: Automatic delegation and backup user mechanisms
- **Custom Approval Rules**: Define custom approval capabilities and conditions
- **Time-based Availability**: Schedule-based availability and working hours
- **Approval Statistics**: Track approval performance and response times

### 📧 Advanced Email Notifications
- **Template-based System**: Create custom email templates for different notification types
- **Conditional Notifications**: Send notifications based on workflow criteria
- **Multiple Recipients**: Support for different recipient types (approver, requester, manager, department)
- **Email Service Management**: Configure multiple SMTP services with failover support
- **Notification Tracking**: Track email delivery, opening, and click rates

### 🔄 Workflow Engine
- **Complete Lifecycle Management**: Handle the entire approval workflow lifecycle
- **Automatic Escalation**: Escalate workflows based on timeouts and conditions
- **Approval Delegation**: Automatic delegation when approvers are unavailable
- **Comprehensive Audit Trail**: Track all approval actions and changes
- **API Integration**: RESTful API for external system integration

## Installation

1. **Download the Module**
   ```bash
   git clone https://github.com/yourcompany/odoo-approval-workflow.git
   ```

2. **Install Dependencies**
   - Odoo 18 Community Edition
   - Python 3.8+
   - Required Python packages: smtplib, email, json, datetime

3. **Install the Module**
   - Copy the module to your Odoo addons directory
   - Update the module list in Odoo
   - Install the "Advanced Approval Workflow System" module

## Configuration

### 1. Email Service Configuration

1. Go to **Approval System > Notifications > Email Services**
2. Create a new email service with your SMTP settings:
   - SMTP Server: Your email server
   - SMTP Port: Usually 587 for TLS or 465 for SSL
   - Authentication: Your email credentials
   - From Email: The sender email address

### 2. Dynamic User Setup

1. Go to **Approval System > Configuration > Dynamic Users**
2. Create dynamic user profiles for your approvers:
   - Link to Odoo users
   - Set approval capabilities
   - Configure availability schedules
   - Set up delegation rules

### 3. Approval Matrix Configuration

1. Go to **Approval System > Configuration > Approval Matrices**
2. Create approval matrices for different scenarios:
   - Amount-based matrices for purchase approvals
   - Department-based matrices for leave requests
   - Category-based matrices for expense reports
   - Custom matrices for specific business rules

### 4. Notification Templates

1. Go to **Approval System > Notifications > Templates**
2. Customize notification templates:
   - Approval request notifications
   - Reminder notifications
   - Approval/rejection notifications
   - Custom notification types

## Usage

### Creating a Workflow

1. Go to **Approval System > Workflows > Create Workflow**
2. Fill in the workflow details:
   - Workflow name and description
   - Workflow type (purchase, expense, leave, etc.)
   - Amount and currency
   - Department and category
3. Submit the workflow for approval

### Approving Workflows

1. Go to **Approval System > Workflows > Pending My Approval**
2. Review the workflow details
3. Click "Approve" or "Reject" with optional comments
4. The system will automatically move to the next approval level

### Managing Approvals

1. **Dashboard**: View approval statistics and recent activities
2. **My Workflows**: Track your submitted workflows
3. **Pending Approvals**: Manage workflows awaiting your approval
4. **Reports**: Generate approval reports and analytics

## API Documentation

### Endpoints

#### Get Workflows
```http
GET /api/approval/workflows
```

**Parameters:**
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 20)
- `state`: Filter by workflow state
- `workflow_type`: Filter by workflow type
- `requester_id`: Filter by requester ID
- `department_id`: Filter by department ID
- `search`: Search term

#### Create Workflow
```http
POST /api/approval/workflows
```

**Request Body:**
```json
{
  "name": "Purchase Request",
  "workflow_type": "purchase",
  "amount": 1000.00,
  "currency_id": 1,
  "department_id": 1,
  "description": "Office supplies purchase"
}
```

#### Approve Workflow
```http
POST /api/approval/workflows/{workflow_id}/approve
```

**Request Body:**
```json
{
  "comments": "Approved for office supplies"
}
```

#### Reject Workflow
```http
POST /api/approval/workflows/{workflow_id}/reject
```

**Request Body:**
```json
{
  "reason": "Budget exceeded"
}
```

### Authentication

All API endpoints require user authentication. Include the session cookie or API key in your requests.

## Customization

### Custom Workflow Types

1. Extend the `workflow_type` selection field in `approval.workflow`
2. Add custom validation logic in the workflow model
3. Create custom views and templates for the new workflow type

### Custom Approval Rules

1. Extend the `custom_rules` field in `dynamic.user`
2. Implement custom validation logic in the user model
3. Add custom approval conditions in the matrix model

### Custom Notification Templates

1. Create new notification templates in the system
2. Define custom template variables
3. Implement custom rendering logic for complex templates

## Security

### Access Control

The module includes comprehensive security features:

- **Role-based Access Control**: Different access levels for managers, users, and approvers
- **Record Rules**: Users can only access their own workflows and assigned approvals
- **API Security**: All API endpoints require authentication
- **Data Encryption**: Sensitive data is encrypted in the database

### Security Groups

- **Approval Manager**: Full access to all approval functions
- **Approval User**: Can create and manage their own workflows
- **Approval Approver**: Can approve workflows assigned to them
- **Notification Manager**: Can manage notification templates and email services

## Troubleshooting

### Common Issues

1. **Email Notifications Not Sending**
   - Check SMTP configuration in Email Services
   - Verify email templates are active
   - Check notification queue for failed emails

2. **Approval Matrix Not Applied**
   - Verify matrix conditions match workflow criteria
   - Check matrix is active and in correct state
   - Ensure approvers are available and have correct permissions

3. **Workflow Not Progressing**
   - Check approval level completion criteria
   - Verify approvers are available
   - Check for timeout and escalation settings

### Debug Mode

Enable debug mode in Odoo to see detailed error messages and logs.

## Support

For support and questions:

- **Documentation**: Check this README and inline help
- **Issues**: Report bugs and feature requests on GitHub
- **Email**: support@yourcompany.com
- **Community**: Join our community forum

## License

This module is licensed under LGPL-3. See the LICENSE file for details.

## Changelog

### Version 1.0.0
- Initial release
- Multi-matrix approval system
- Dynamic user management
- Email notification system
- RESTful API
- Comprehensive reporting

## Contributing

We welcome contributions! Please see our contributing guidelines for details.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Roadmap

### Upcoming Features
- Mobile app integration
- Advanced analytics and reporting
- Workflow automation rules
- Integration with external systems
- Multi-language support
- Advanced notification channels (SMS, Slack, etc.)

---

**Made with ❤️ for the Odoo Community**
