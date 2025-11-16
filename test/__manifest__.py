# -*- coding: utf-8 -*-
{
    'name': 'Budget Management System',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Advanced budget management with automatic tracking, overbudget notifications, and approval system',
    'description': """
Advanced Budget Management System for Odoo 18 Community Edition
===============================================================

This module provides a comprehensive budget management system with the following features:

**Automatic Budget Management:**
- Automatic budget tracking across all Odoo modules
- Real-time budget commitment and actual spending tracking
- Automatic overbudget detection and notifications
- Budget utilization monitoring and alerts

**Overbudget Handling:**
- Automatic overbudget detection when budget is exceeded
- Overbudget notifications with email alerts
- Overbudget approval workflow integration
- Configurable overbudget thresholds and rules

**Universal Module Integration:**
- Seamless integration with Purchase Orders
- Integration with Sale Orders, Journal Entries, HR Expenses
- Integration with Project Tasks and all other Odoo modules
- Automatic budget commitment creation and release

**Advanced Features:**
- Multi-level budget approval system
- Department and project-based budget allocation
- Analytic account integration
- Budget variance analysis and reporting
- Real-time budget dashboard and analytics

**Key Features:**
- Automatic budget monitoring and alerts
- Overbudget approval workflows
- Universal module integration
- Real-time notifications and email alerts
- Comprehensive reporting and analytics
- Multi-currency support
- Role-based access control

**Supported Modules:**
- Purchase Orders (purchase.order)
- Sale Orders (sale.order)
- Journal Entries (account.move)
- HR Expenses (hr.expense)
- Project Tasks (project.task)
- All custom modules

**Integration:**
- Seamless integration with existing Odoo modules
- Automatic budget commitment tracking
- Real-time budget status updates
- Email notification system
- Approval workflow integration

**Security:**
- Role-based access control
- Budget approval workflows
- Audit trail for all budget changes
- Secure API for external integrations

This module is designed for organizations that need comprehensive budget control and monitoring across all business processes.
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'hr',
        'hr_expense',
        'account',
        'purchase',
        'sale',
        'project',
        'web',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        'security/approval_security.xml',
        
        # Data
        'data/approval_data.xml',
        'data/budget_data.xml',
        
        # Views
        'views/approval_workflow_views.xml',
        'views/multi_matrix_views.xml',
        'views/dynamic_user_views.xml',
        'views/notification_views.xml',
        'views/budget_views.xml',
        'views/budget_menus.xml',
        
        # Menus
        'views/approval_menus.xml',
        
        # Wizards
        'wizards/approval_wizard_views.xml',
        
        # Reports
        'reports/approval_reports.xml',
        'reports/budget_reports.xml',
    ],
    'demo': [
        'demo/approval_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'budget_management/static/src/css/approval_workflow.css',
            'budget_management/static/src/js/approval_workflow.js',
            'budget_management/static/src/xml/approval_workflow_templates.xml',
        ],
        'web.assets_frontend': [
            'budget_management/static/src/css/approval_workflow_frontend.css',
            'budget_management/static/src/js/approval_workflow_frontend.js',
        ],
    },
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'sequence': 10,
    'price': 0.0,
    'currency': 'USD',
    'support': 'support@yourcompany.com',
    'maintainers': ['Your Company'],
    'external_dependencies': {
        'python': [
            'smtplib',
            'email',
            'json',
            'datetime',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}