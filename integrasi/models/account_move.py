import requests
import time
from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    x_bc_invoice_number = fields.Char(string="No. Invoice BC", readonly=True)

    def _get_valid_token(self):
        config = self.env['ir.config_parameter'].sudo()
        token = config.get_param('bc_integration.access_token')
        expiry = config.get_param('bc_integration.access_token_expiry')
        now = int(time.time())
        if not token or not expiry or now > int(expiry) - 60:
            token = self._get_bc_token()
        return token

    def _get_bc_token(self):
        config = self.env['ir.config_parameter'].sudo()
        client_id = config.get_param('bc_integration.client_id')
        client_secret = config.get_param('bc_integration.client_secret')
        tenant_id = config.get_param('bc_integration.tenant_id')
        url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'https://api.businesscentral.dynamics.com/.default'
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        response = requests.post(url, data=data, headers=headers)
        if response.status_code == 200:
            resp_json = response.json()
            access_token = resp_json.get('access_token')
            expires_in = resp_json.get('expires_in', 600)
            expiry = int(time.time()) + int(expires_in)
            config.set_param('bc_integration.access_token', access_token)
            config.set_param('bc_integration.access_token_expiry', str(expiry))
            return access_token
        else:
            raise Exception(f"Gagal mendapatkan token: {response.text}")

    def action_send_to_bc_purchase_invoice(self):
        token = self._get_valid_token()
        config = self.env['ir.config_parameter'].sudo()
        company_id = config.get_param('bc_integration.company_id')
        tenant_id = config.get_param('bc_integration.tenant_id')
        url = f"https://api.businesscentral.dynamics.com/v2.0/{tenant_id}/Production/ODataV4/Company({company_id})/Purchinv"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        header_data = {
            "Document_Type": "Invoice",
            "Buy_from_Vendor_Name": self.partner_id.name or "",
        }

        response = requests.post(url, json=header_data, headers=headers)
        if response.status_code in (200, 201):
            bc_invoice_data = response.json()
            bc_invoice_no = bc_invoice_data.get('No') or bc_invoice_data.get('Document_No')
            if bc_invoice_no:
                self.x_bc_invoice_number = bc_invoice_no
                self.message_post(body=f"✅ Invoice BC berhasil dibuat: {bc_invoice_no}")
            else:
                self.message_post(body="⚠️ Header terkirim, tapi tidak mendapatkan nomor invoice.")
        else:
            self.message_post(body=f"❌ Gagal kirim header ke BC: {response.text}")

    def action_send_lines_to_bc(self):
        if not self.x_bc_invoice_number:
            self.message_post(body="❌ Gagal kirim lines: No. Invoice BC belum tersedia.")
            return

        token = self._get_valid_token()
        config = self.env['ir.config_parameter'].sudo()
        company_id = config.get_param('bc_integration.company_id')
        tenant_id = config.get_param('bc_integration.tenant_id')
        url = f"https://api.businesscentral.dynamics.com/v2.0/{tenant_id}/Production/ODataV4/Company({company_id})/purchaseInvoiceLines"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        line_number = 10000

        for line in self.invoice_line_ids:
            if not line.product_id:
                self.message_post(body=f"⚠️ Line '{line.name}' dilewati karena tidak memiliki product.")
                continue

            line_data = {
                "Document_Type": "Invoice",
    "Document_No": self.x_bc_invoice_number,
    "Line_No": line_number,
    "Description": line.name or line.product_id.name,
    "Quantity": float(line.quantity or 0),
    "Direct_Unit_Cost": float(line.price_unit or 0),
    "Type": "Item",
    "No": line.product_id.default_code or "", 
            }

            response = requests.post(url, json=line_data, headers=headers)
            if response.status_code in (200, 201):
                self.message_post(body=f"✅ Line '{line.name}' berhasil dikirim ke BC.")
            else:
                self.message_post(body=f"❌ Gagal kirim line '{line.name}' ke BC: {response.text}")

            line_number += 10000

    def action_send_invoice_and_lines(self):
        """Tombol utama: kirim header, tunggu 1 menit, kirim lines"""
        self.action_send_to_bc_purchase_invoice()
        if self.x_bc_invoice_number:
            self.message_post(body="⏳ Menunggu 60 detik sebelum kirim lines...")
            time.sleep(60)
            self.action_send_lines_to_bc()
