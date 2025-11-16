{
    'name': 'New Approval',
    'version': '1.0',
    'author': 'Assistant AI',
    'category': 'Tools',
    'summary': 'New multi-level approval with email and link approve',
    'depends': ['base', 'mail'],
    'data': [
        'data/ir_model_data.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/email_template.xml',
        'views/approval_views.xml',
    ],
    'installable': True,
    'application': False,
}
