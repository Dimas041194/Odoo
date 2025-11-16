{
    'name': 'BC Payment Webhook',
    'version': '1.0',
    'summary': 'Endpoint untuk webhook Business Central',
    'author': 'Nama Anda',
    'category': 'Tools',
    'depends': ['base','account'],
    'data': [
        'data/cron.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',  # <-- Tambahkan baris ini
}
