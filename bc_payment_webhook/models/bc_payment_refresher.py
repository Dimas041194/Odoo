import requests
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class BCPaymentRefresher(models.Model):
    _name = 'bc.payment.refresher'
    _description = 'Manual Refresher Pembayaran dari Business Central'

    @api.model
    def refresh_payment_for_invoice(self, invoice):
        if not invoice.x_bc_invoice_number:
            invoice.message_post(body="⚠️ Invoice belum punya nomor dari Business Central.")
            return

        token = invoice._get_valid_token()
        config = self.env['ir.config_parameter'].sudo()
        company_id = config.get_param('bc_integration.company_id')
        tenant_id = config.get_param('bc_integration.tenant_id')
        env = 'Production'  # Ganti ke 'Sandbox' jika perlu

        url = (
            f"https://api.businesscentral.dynamics.com/v2.0/{tenant_id}/{env}/ODataV4/"
            f"Company({company_id})/generalLedgerEntries?"
            f"$filter=External_Document_No eq '{invoice.x_bc_invoice_number}' and Document_Type eq 'Payment'"
        )

        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

        try:
           
            response = requests.get(url, headers=headers)
            _logger.info(f"BC Payment Sync URL: {url}")
            _logger.info(f"BC Payment Sync Response Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                payments = result.get('value', [])
                _logger.info(f"All Payments Response: {payments}")

               
                filtered_payments = [
                    p for p in payments
                    if p.get('Document_Type') == 'Payment' and float(p.get('Debit_Amount', 0)) > 0
                ]
                _logger.info(f"Filtered Payments (Debit_Amount > 0): {filtered_payments}")

               
                total_paid = sum(float(p.get('Debit_Amount', 0)) for p in filtered_payments)
                invoice_amount = abs(invoice.amount_total)

                _logger.info(f"Total Paid: {total_paid}, Invoice Amount: {invoice_amount}")

                if total_paid >= invoice_amount and invoice_amount > 0:
                    if not invoice.x_bc_payment_notified:
                        invoice.message_post(body="✅ Invoice otomatis ditandai LUNAS dari Business Central.\n"
                                                  f"Total tagihan: {invoice_amount}.")
                        invoice.x_bc_payment_notified = True
                        invoice.x_bc_partial_payment_notified = False
                        invoice.x_bc_no_payment_notified = False

                        if invoice.state == 'draft':
                            invoice.action_post()
                            _logger.info(f"Invoice {invoice.name} diposting sebagai LUNAS.")

                elif 0 < total_paid < invoice_amount:
                    if not invoice.x_bc_partial_payment_notified:
                        invoice.message_post(
                            body=f"🟡 Pembayaran sebagian terdeteksi dari Business Central.\n"
                                 f"Total tagihan: {invoice_amount}, Pembayaran: {total_paid}."
                        )
                        invoice.x_bc_partial_payment_notified = True
                        invoice.x_bc_payment_notified = False
                        invoice.x_bc_no_payment_notified = False

                else:
                    if not invoice.x_bc_no_payment_notified:
                        invoice.message_post(
                            body=f"❌ Tidak ada pembayaran terdeteksi di Business Central.\n"
                                 f"Total tagihan: {invoice_amount}, Pembayaran: {total_paid}."
                        )
                        invoice.x_bc_no_payment_notified = True
                        invoice.x_bc_payment_notified = False
                        invoice.x_bc_partial_payment_notified = False

            else:
                invoice.message_post(body=f"❌ Gagal mengambil data dari Business Central "
                                          f"({response.status_code} - {response.text})")

        except Exception as e:
            _logger.error(f"❌ Error sinkronisasi pembayaran dari Business Central: {str(e)}")
            

    @api.model
    def cron_refresh_bc_payments(self):
        invoices = self.env['account.move'].sudo().search([
            ('x_bc_invoice_number', '!=', False),
            ('state', '!=', 'paid'),
        ])
        for invoice in invoices:
            self.refresh_payment_for_invoice(invoice)
