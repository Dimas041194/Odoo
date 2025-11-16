{
    'name': 'Custom Multi-Level Approval',
    'version': '1.0',
    'category': 'Custom',
    'summary': 'Multi-level approval workflow for any model',
    'author': 'Your Name',
    'depends': ['mail', 'purchase', 'project'],
    'data': [
        'security/approval_security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/email_template.xml',
        'data/scheduler_data.xml',
        'views/approval_flow_views.xml',
        'views/approval_request_views.xml',
    ],
    'installable': True,
    'application': False,
}
