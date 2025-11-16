
from odoo import fields, models


class HrContributionRegister(models.Model):
    """Create a new model for adding fields."""
    _name = 'hr.contribution.register'
    _description = 'Contribution Register'

    company_id = fields.Many2one(
        comodel_name='res.company', string='Company',
        help="Choose Company for Register",
        default=lambda self: self.env['res.company']._company_default_get())
    partner_id = fields.Many2one('res.partner', string='Partner',
                                 help="Choose Partner for Register")
    name = fields.Char(required=True, string="Name",
                       help="Contribution Register Name")
    register_line_ids = fields.One2many('hr.payslip.line',
                                        'register_id',
                                        string='Register Line',
                                        readonly=True,
                                        help="Choose Payslip line")
    note = fields.Text(string='Description',
                       help="Set Description for Register")
