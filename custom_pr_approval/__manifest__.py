{
    'name': 'Custom Purchase Request with Multi-level Approval',
    'version': '1.0',
    'category': 'Purchases',
    'summary': 'Custom Purchase Request and Approval Workflow with integration to Purchase Order',
    'depends': ['purchase'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/purchase_request_views.xml',
        'views/purchase_request_line_views.xml',
        'views/approval_flow_views.xml',
        'views/approval_request_views.xml',
        'views/purchase_order_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
