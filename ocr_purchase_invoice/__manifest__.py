{
    'name': 'OCR AI for Purchase Invoice',
    'version': '18.0.1.0.0',
    'category': 'Purchase',
    'summary': 'Integrasi OCR AI untuk ekstrak data invoice otomatis',
    'description': """
        Modul custom untuk demo: Upload invoice gambar/PDF, ekstrak data dengan OCR,
        dan isi otomatis ke purchase invoice.
    """,
    'author': 'Your Name',
    'depends': ['purchase', 'account'],
    'data': [
        'views/purchase_invoice_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'external_dependencies': {
        'python': ['pytesseract', 'pillow', 'pdf2image'],
    },
}
