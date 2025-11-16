# custom_approval/__manifest__.py
{
    'name': 'Custom Multi-Level Approval',
    'version': '1.0',
    'author': 'Dimas Aryo Novantri',
    'category': 'Tools',
    'summary': 'Approval bertingkat multi-level dengan email dan link approve',
    'depends': ['base', 'mail'],
    'data': [
    'data/ir_model_data.xml',    # harus yang pertama supaya model sudah dikenali
    'security/ir.model.access.csv',  # baru load hak akses setelah model ada
    'data/ir_sequence_data.xml',
    'data/email_template.xml',
    'views/approval_views.xml',
],

    'installable': True,
    'application': False,
}
