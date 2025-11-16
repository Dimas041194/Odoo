from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    nik = fields.Char(string="NIK", required=True)
    enrollment_status = fields.Selection([
        ('pre', 'Pre-Registered'),
        ('form_paid', 'Form Paid'),
        ('docs_submitted', 'Documents Submitted'),
        ('screened', 'Screened'),
        ('admitted', 'Admitted'),
        ('rejected', 'Rejected'),
        ('registered', 'Registered'),
        ('active', 'Active'),
    ], string="Enrollment Status", default='pre')

    _sql_constraints = [
        ('unique_nik', 'unique(nik)', 'NIK sudah pernah terdaftar!')
    ]

    # Only partners created via the form show in menu
    is_enrollment = fields.Boolean(default=True)

    @api.model
    def create(self, vals):
        vals['name'] = '[PRE] %s' % vals.get('name')
        return super().create(vals)
