from odoo import http
from odoo.http import request
import json
import re
import requests
import logging

_logger = logging.getLogger(__name__)

class BCPaymentWebhookController(http.Controller):

    @http.route('/bc/payment_webhook', type='http', auth="none", csrf=False, methods=['GET', 'POST'])
    def bc_webhook(self, **kw):
        validation_token = request.httprequest.args.get('validationToken')
        if validation_token:
            return request.make_response(validation_token, headers=[('Content-Type', 'text/plain')])

        if request.httprequest.method == 'POST':
            try:
                payload = request.httprequest.get_data(as_text=True)
                _logger.info(f"\ud83d\udce5 Webhook BC masuk. Payload: {payload}")
                data = json.loads(payload) if payload else {}

               
                if 'value' in data and isinstance(data['value'], list):
                    resource_info = data['value'][0].get('resource', '')
                    match = re.search(r'generalLedgerEntries\(([^)]+)\)', resource_info)
                    gle_id = match.group(1) if match else None

                    if not gle_id:
                        return request.make_response('GLE ID tidak valid dalam resource', status=400)

                    gle_data = self._get_bc_general_ledger_entry(gle_id)
                    bc_invoice_no = gle_data.get('externalDocumentNumber')
                    document_type = gle_data.get('documentType')

                    if bc_invoice_no and document_type and document_type.lower() == 'payment':
                        invoice = request.env['account.move'].sudo().search([
                            ('x_bc_invoice_number', '=', bc_invoice_no)
                        ], limit=1)
                        if invoice:
                            request.env['bc.payment.refresher'].sudo().refresh_payment_for_invoice(invoice)
                            return request.make_response('Invoice processed via webhook', status=200)
                        else:
                            return request.make_response('Invoice tidak ditemukan', status=404)

                    return request.make_response('GLE data tidak lengkap atau bukan payment', status=400)

               
                bc_invoice_no = data.get('externalDocumentNumber') or data.get('No') or data.get('Document_No')
                document_type = data.get('documentType') or data.get('Payment_Status') or data.get('status')

                if bc_invoice_no and document_type and document_type.lower() == 'payment':
                    invoice = request.env['account.move'].sudo().search([
                        ('x_bc_invoice_number', '=', bc_invoice_no)
                    ], limit=1)
                    if invoice:
                        request.env['bc.payment.refresher'].sudo().refresh_payment_for_invoice(invoice)
                        return request.make_response('Invoice processed via manual trigger', status=200)
                    else:
                        return request.make_response('Invoice tidak ditemukan', status=404)

                return request.make_response('Payload tidak valid untuk proses invoice', status=400)

            except Exception as e:
                request.env['ir.logging'].sudo().create({
                    'name': 'BC Payment Webhook Error',
                    'type': 'server',
                    'level': 'ERROR',
                    'dbname': request.env.cr.dbname,
                    'message': str(e),
                    'path': 'bc_payment_webhook',
                    'line': '0',
                    'func': 'bc_webhook',
                })
                return request.make_response(f'Error: {str(e)}', status=500)

        return request.make_response("OK", status=200)

    def _get_bc_general_ledger_entry(self, gle_id):
        config = request.env['ir.config_parameter'].sudo()
        tenant_id = config.get_param('bc_integration.tenant_id')
        company_id = config.get_param('bc_integration.company_id')
        env = 'Production'  # atau 'Sandbox' jika kamu pakai environment itu

       
        token = request.env['account.move'].sudo()._get_valid_token()

        url = f"https://api.businesscentral.dynamics.com/v2.0/{tenant_id}/{env}/ODataV4/Company({company_id})/generalLedgerEntries({gle_id})"
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Gagal ambil data GLE dari BC: {response.status_code} - {response.text}")
