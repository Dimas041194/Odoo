
from odoo import fields, models


class HrLeaveType(models.Model):
    """Inherit hr_leave_type for adding code."""
    _inherit = "hr.leave.type"
    _description = "Time Off Type"

    code = fields.Char(string="Code", help="Code for Time Off Type")
