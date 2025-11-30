{
    "name": "ERP Employee Import",
    "version": "18.0.1.0.0",
    "summary": "Async Employee Import from Excel",
    "description": "Import karyawan dari file Excel (xlsx) dengan background job dan email notifikasi.",
    "author": "Dimas Aryo Novantri",
    "category": "Human Resources",
    "license": "LGPL-3",
    "depends": ["hr", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_employee_import.xml",
        "data/mail_template_employee_import.xml",
        "views/employee_import_views.xml",
    ],
    "installable": True,
    "application": False,
}
