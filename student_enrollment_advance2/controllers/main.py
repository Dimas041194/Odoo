import base64
from odoo import http
from odoo.http import request


class EnrollmentWebsite(http.Controller):
    @http.route('/enrollment/register', type='http', auth='public', website=True)
    def enrollment_form(self, **kwargs):
        return request.render('student_enrollment_advanced.website_enrollment_form')

    @http.route('/enrollment/register/submit', type='http', auth='public', website=True, methods=['POST'])
    def enrollment_submit(self, **post):
        name = post.get('name')
        nik = post.get('nik')
        email = post.get('email')
        phone = post.get('phone')
        attachment_file = request.httprequest.files.get('attachment')

        # Cek apakah NIK sudah terdaftar
        if request.env['res.partner'].sudo().search([('nik', '=', nik)], limit=1):
            return request.render('student_enrollment_advanced.error_duplicate_nik', {'nik': nik})

        # Cek apakah file diupload
        if not attachment_file:
            return request.render('student_enrollment_advanced.error_attachment_missing')

        # Membuat record partner baru
        partner = request.env['res.partner'].sudo().create({
            'name': '[PRE] %s' % name,
            'nik': nik,
            'email': email,
            'phone': phone,
            'enrollment_status': 'pre',
            'customer_rank': 1,
            'is_enrollment': True
        })

        # Simpan attachment ke ir.attachment yang berelasi dengan partner
        attachment = request.env['ir.attachment'].sudo().create({
            'name': attachment_file.filename,
            'type': 'binary',
            'datas': base64.b64encode(attachment_file.read()),
            'res_model': 'res.partner',
            'res_id': partner.id,
            'mimetype': attachment_file.content_type,
        })

        # Render template sukses dengan data attachment
        return request.render('student_enrollment_advanced.enrollment_success', {
            'partner': partner,
            'nik': nik,
            'name': name,
            'email': email,
            'phone': phone,
            'attachment': attachment,
        })
