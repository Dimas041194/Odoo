{
    'name': 'Student Enrollment Advanced Website',
    'version': '1.0',
    'author': 'Your Name',
    'category': 'Website',
    'summary': 'Advanced Initial Registration for Student Enrollment',
    'depends': ['base', 'website', 'contacts', 'mail'],
    'data': [
        'views/website_enrollment_templates.xml',
        'views/partner_views.xml',
        'data/email_templates.xml',
        'security/ir.model.access.csv',
    ],
    'assets': {
        'web.assets_frontend': [
            # isi jika ada asset css/js custom, pastikan path benar TANPA slash di depan
            # 'student_enrollment_advanced/static/src/css/website_enroll.css',
            # 'student_enrollment_advanced/static/src/js/website_enroll.js'
        ],
    },
    'installable': True,
    'application': True,
}
