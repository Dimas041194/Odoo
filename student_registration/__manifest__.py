{
    'name': 'Educational Student Registration',
    'version': '1.0',
    'category': 'Education',
    'author': 'Your Name',
    'depends': ['base', 'mail', 'crm', 'website'],
    'data': [
    'views/student_registration_form_template.xml',
    'views/registration_confirmation_template.xml',
    'views/student_registration_views.xml',
    'views/email_template.xml',
    'views/admin_view.xml',
    'security/ir.model.access.csv',
],

    'installable': True,
}
