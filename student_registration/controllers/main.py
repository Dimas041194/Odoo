import base64
import logging
from odoo import http
from odoo.http import request
from reportlab.pdfgen import canvas
from io import BytesIO

_logger = logging.getLogger(__name__)

class StudentRegistrationController(http.Controller):

    @http.route('/student/form', type='http', auth='public', website=True)
    def student_form(self, **kwargs):
        return request.render('student_registration.student_registration_form')

    def _generate_registration_pdf(self, student_record):
        buffer = BytesIO()
        c = canvas.Canvas(buffer)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, 800, "Bukti Pendaftaran Siswa Baru")
        c.setFont("Helvetica", 12)
        y = 770
        c.drawString(50, y, f"Nama: {student_record.name or '-'}")
        y -= 20
        c.drawString(50, y, f"NIK: {student_record.nik or '-'}")
        y -= 20
        c.drawString(50, y, f"Alamat: {student_record.address or '-'}")
        y -= 20
        c.drawString(50, y, f"Email: {student_record.email or '-'}")
        c.save()
        pdf = buffer.getvalue()
        buffer.close()
        return pdf

    @http.route('/student/registration', type='http', auth='public', website=True, csrf=False)
    def student_registration(self, **kwargs):
        name = kwargs.get('name')
        nik = kwargs.get('nik')
        address = kwargs.get('address')
        email = kwargs.get('email')

        # Dokumen
        documents_file = kwargs.get('documents')
        documents_base64 = False
        documents_filename = False
        if documents_file:
            documents_content = documents_file.read()
            documents_base64 = base64.b64encode(documents_content)
            documents_filename = getattr(documents_file, 'filename', 'Dokumen_Siswa.pdf')

        # Foto siswa
        photo_file = kwargs.get('photo')
        photo_base64 = False
        photo_filename = False
        if photo_file:
            photo_content = photo_file.read()
            photo_base64 = base64.b64encode(photo_content).decode('utf-8')
            photo_filename = getattr(photo_file, 'filename', 'Foto_Siswa.jpg')

        if not name:
            return request.render('student_registration.student_registration_form', {
                'error': 'Nama Lengkap harus diisi'
            })

        student_record = request.env['student.registration'].sudo().create({
            'name': name,
            'nik': nik,
            'address': address,
            'email': email,
            'documents': documents_base64,
            'documents_filename': documents_filename,
            'photo': photo_base64,
            'photo_filename': photo_filename,
        })

        request.env['crm.lead'].sudo().create({
            'name': f'Siswa Baru: {name}',
            'contact_name': name,
            'email_from': email,
            'phone': kwargs.get('phone'),
            'partner_name': name,
            'description': f'Pendaftaran siswa baru, NIK: {nik}, Alamat: {address}',
            'type': 'lead',
            'stage_id': 1,
        })

        # Buat ir.attachment untuk dokumen upload (supaya bisa didownload di backend)
        attachments = []

        if documents_base64 and documents_filename:
            attachment = request.env['ir.attachment'].sudo().create({
                'name': documents_filename,
                'type': 'binary',
                'datas': documents_base64,
                'res_model': 'student.registration',
                'res_id': student_record.id,
                'mimetype': 'application/pdf',
            })
            attachments.append((attachment.name, base64.b64decode(documents_base64)))

        # Tambahkan attachment PDF bukti pendaftaran otomatis
        pdf_content = self._generate_registration_pdf(student_record)
        if pdf_content:
            pdf_name = "Bukti_Pendaftaran_%s.pdf" % (student_record.name.replace(' ', '_'))
            attachments.append((pdf_name, pdf_content))

        email_status = ""
        try:
            template = request.env.ref('student_registration.email_template_confirmation').sudo()
            mail_id = template.send_mail(
                student_record.id,
                force_send=True,
                email_values={
                    'email_from': 'dimasaryonovantri04@gmail.com',
                    'email_to': email,
                    'attachments': attachments
                }
            )
            email_status = "Email konfirmasi & lampiran berhasil dikirim ke siswa."
            _logger.info(f"Email konfirmasi terkirim ke {student_record.email} untuk siswa {student_record.name}")
        except Exception as e:
            email_status = f"Gagal mengirim email konfirmasi: {e}"
            _logger.error(f"Gagal mengirim email konfirmasi: {e}")

        try:
            admin_template = request.env.ref('student_registration.email_template_admin').sudo()
            admin_template.send_mail(
                student_record.id,
                force_send=True,
                email_values={
                    'email_from': 'dimasaryonovantri04@gmail.com',
                    'email_to': 'dimasaryonovantri04@gmail.com'
                }
            )
            _logger.info("Email notifikasi admin berhasil dikirim")
        except Exception as e:
            _logger.error(f"Gagal mengirim email notifikasi admin: {e}")

        return request.render('student_registration.registration_confirmation', {
            'student_name': name,
            'email_status': email_status,
        })

class StudentRegistrationAttachmentController(http.Controller):

    @http.route('/student/registration/download/', type='http', auth='public', website=True)
    def download_attachment(self, registration_id, **kwargs):
        registration = request.env['student.registration'].sudo().browse(registration_id)
        if not registration or not registration.documents:
            return request.not_found()
        filename = "Dokumen_Pendaftaran_%s.pdf" % (registration.name or "Siswa")
        file_content = base64.b64decode(registration.documents)
        return request.make_response(
            file_content,
            [('Content-Type', 'application/pdf'),
            ('Content-Disposition', 'attachment; filename=%s' % filename)]
        )

    @http.route('/student/registration/printout/', type='http', auth='public', website=True)
    def registration_printout(self, registration_id, **kwargs):
        registration = request.env['student.registration'].sudo().browse(registration_id)
        if not registration:
            return request.not_found()
        return request.render('student_registration.registration_printout', {
            'student': registration,
        })
