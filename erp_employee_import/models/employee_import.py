from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import io
import logging

_logger = logging.getLogger(__name__)

try:
    import openpyxl
except ImportError:
    openpyxl = None


class HrEmployeeImportWizard(models.TransientModel):
    _name = "hr.employee.import.wizard"
    _description = "Employee Import Wizard"

    file_data = fields.Binary(string="Excel File", required=True)
    filename = fields.Char(string="File Name")

    def action_import(self):
        self.ensure_one()
        if not self.file_data or not self.filename:
            raise UserError(_("Please upload an Excel file."))

        if not self.filename.lower().endswith(".xlsx"):
            raise UserError(_("Invalid file format. Please upload an .xlsx file."))

        if not openpyxl:
            raise UserError(_("Python package 'openpyxl' is required on the server."))

        job = self.env["hr.employee.import.job"].create({
            "user_id": self.env.user.id,
            "file_data": self.file_data,
            "filename": self.filename,
        })
        _logger.info("Created employee import job %s", job.id)
        return {"type": "ir.actions.act_window_close"}


class HrEmployeeImportJob(models.Model):
    _name = "hr.employee.import.job"
    _description = "Employee Import Job"
    _order = "create_date desc"

    state = fields.Selection([
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("done", "Done"),
        ("failed", "Failed"),
    ], default="pending", required=True)
    user_id = fields.Many2one("res.users", string="Requested By", required=True)
    file_data = fields.Binary(string="Excel File", required=True)
    filename = fields.Char(string="File Name", required=True)
    log = fields.Text(string="Log")
    total_rows = fields.Integer(string="Total Rows")
    success_count = fields.Integer(string="Success Count")
    failed_count = fields.Integer(string="Failed Count")

    def _decode_file(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_("No file to process."))
        try:
            data = base64.b64decode(self.file_data)
            return io.BytesIO(data)
        except Exception as e:
            _logger.error("Error decoding file for job %s: %s", self.id, e)
            raise UserError(_("Failed to decode file."))

    def _create_employee_from_row(self, vals):
        self.ensure_one()
        email = vals.get("work_email")
        if email:
            existing = self.env["hr.employee"].sudo().search([
                ("work_email", "=", email)
            ], limit=1)
            if existing:
                raise UserError(_("Duplicate employee with email %s") % email)

        return self.env["hr.employee"].sudo().create(vals)

    def action_process(self):
        for job in self:
            if job.state not in ("pending", "failed"):
                continue

            job.write({"state": "processing"})
            log_lines = []
            success = 0
            failed = 0
            total = 0

            try:
                buffer = job._decode_file()
                wb = openpyxl.load_workbook(buffer, read_only=True, data_only=True)
                sheet = wb.active

                header_map = {}
                first = True

                for row in sheet.iter_rows(values_only=True):
                    if first:
                        first = False
                        for idx, col in enumerate(row):
                            if not col:
                                continue
                            header_map[str(col).strip().lower()] = idx
                        required_cols = ["name"]
                        for colname in required_cols:
                            if colname not in header_map:
                                raise UserError(_("Missing required column '%s'") % colname)
                        continue

                    total += 1
                    try:
                        name = row[header_map.get("name")]
                        work_email = None
                        work_phone = None
                        job_title = None

                        if "work_email" in header_map:
                            work_email = row[header_map.get("work_email")]
                        if "work_phone" in header_map:
                            work_phone = row[header_map.get("work_phone")]
                        if "job_title" in header_map:
                            job_title = row[header_map.get("job_title")]

                        if not name:
                            raise UserError(_("Name is required."))

                        vals = {
                            "name": name,
                            "work_email": work_email or False,
                            "work_phone": work_phone or False,
                            "job_title": job_title or False,
                        }
                        emp = job._create_employee_from_row(vals)
                        success += 1
                        log_lines.append("Row %s: SUCCESS (employee id %s)" % (total, emp.id))
                    except Exception as e:
                        failed += 1
                        _logger.error(
                            "Employee import error in job %s row %s: %s",
                            job.id, total, e
                        )
                        log_lines.append("Row %s: FAILED (%s)" % (total, str(e)))

                job.write({
                    "state": "done",
                    "total_rows": total,
                    "success_count": success,
                    "failed_count": failed,
                    "log": "\n".join(log_lines),
                })
                _logger.info(
                    "Employee import job %s done: total=%s, success=%s, failed=%s",
                    job.id, total, success, failed
                )

                template = job.env.ref(
                    "erp_employee_import.mail_employee_import_result",
                    raise_if_not_found=False,
                )
                if template:
                    template.sudo().send_mail(job.id, force_send=True)

            except Exception as e:
                _logger.error("Fatal error processing employee import job %s: %s", job.id, e)
                job.write({
                    "state": "failed",
                    "log": (job.log or "") + "\nFATAL: %s" % str(e),
                })
