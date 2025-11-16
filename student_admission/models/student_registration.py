from odoo import models, fields, api
from odoo.exceptions import UserError

class StudentRegistration(models.Model):
    _name = 'student.registration'
    _description = 'Student Registration'
    _inherit = ['mail.thread']

    name = fields.Char('Nama Lengkap', required=True)
    nik = fields.Char('NIK', required=True)
    address = fields.Text('Alamat', required=True)
    email = fields.Char('Email')
    photo = fields.Binary('Foto Siswa', attachment=True)
    photo_filename = fields.Char('Nama File Foto')
    documents = fields.Binary('Upload Dokumen', attachment=True)
    documents_filename = fields.Char('Nama File Dokumen')
    payment_proof = fields.Binary('Bukti Pembayaran', attachment=True)
    payment_proof_filename = fields.Char('Nama File Bukti Pembayaran')
    test_score = fields.Integer('Nilai Tes', default=0)
    payment_verified_by = fields.Many2one('res.users', string='Pegawai Verifikasi')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('registered', 'Terdaftar'),
        ('paid', 'Sudah Bayar'),
        ('screened', 'Screening Dokumen'),
        ('tested', 'Tes Siswa'),
        ('accepted', 'Diterima'),
        ('rejected', 'Ditolak'),
    ], default='draft', tracking=True)

    @api.onchange('name', 'nik', 'address', 'documents', 'payment_proof')
    def _onchange_documents_complete(self):
        if self.name and self.nik and self.address and self.documents and self.payment_proof:
            self.state = 'registered'

    def action_mark_as_paid(self):
        if self.state != 'registered':
            raise UserError('Hanya data dengan status "Terdaftar" dapat diproses bayar!')
        self.write({'state': 'paid', 'payment_verified_by': self.env.user.id})

    def action_verify_documents(self):
        if self.state != 'paid':
            raise UserError('Dokumen hanya bisa diverifikasi untuk yang sudah bayar!')
        self.write({'state': 'screened'})

    def action_pass_test(self):
        if self.state != 'screened':
            raise UserError('Tes hanya untuk data yang sudah screening dokumen!')
        self.write({'state': 'tested'})

    def action_accept(self):
        if self.state != 'tested':
            raise UserError('Status diterima hanya untuk peserta yang lulus tes!')
        self.write({'state': 'accepted'})

    def action_reject(self):
        if self.state != 'tested':
            raise UserError('Hanya peserta yang selesai tes bisa ditolak!')
        self.write({'state': 'rejected'})
