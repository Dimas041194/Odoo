{
    'name': 'Latihan Modul',
    'version': '1.0.0',
    'summary': 'Modul latihan Purchase Request',
    'description': """
        Modul latihan untuk membuat Purchase Request yang terhubung ke Purchase Order.
    """,
    'author': 'Nama Anda',
    'website': 'https://www.yourwebsite.com',
    'category': 'Purchases',
    'license': 'LGPL-3',
    'depends': ['base', 'purchase', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_request_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
