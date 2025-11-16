from odoo import models, fields

class StudentRegistration(models.Model):
    _name = 'student.registration'
    _description = 'Student Registration'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nama Lengkap', required=True, tracking=True)
    nik = fields.Char(string='NIK', required=True, tracking=True)
    address = fields.Text(string='Alamat', required=True, tracking=True)
    email = fields.Char(string='Email', tracking=True)

    photo = fields.Binary(string='Foto Siswa', attachment=True)
    photo_filename = fields.Char(string='Nama File Foto')

    documents = fields.Binary(string='Upload Dokumen')
    documents_filename = fields.Char(string='Nama File Dokumen')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed')
    ], default='draft', tracking=True)
