{
    'name': 'Student Admission',
    'version': '1.0',
    'summary': 'Modul Penerimaan Siswa dengan Workflow, Pembayaran, Screening, dan Tes',
    'description': 'Sistem workflow digital penerimaan siswa untuk sekolah modern.',
    'author': 'Nama Anda',
    'category': 'Education',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/student_registration_views.xml',
        'views/student_registration_workflow.xml',
    ],
    'installable': True,
    'application': True,
}
