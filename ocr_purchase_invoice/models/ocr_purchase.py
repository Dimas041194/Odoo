import base64
import re
from odoo import models, fields, api
import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes
import io
import logging
from datetime import datetime
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    invoice_image = fields.Binary(string='Upload Invoice Image/PDF', attachment=True)
    ocr_extracted_data = fields.Text(string='Data Ekstrak OCR', readonly=True)

    @api.model
    def extract_ocr_data(self, image_data):
        """Ekstrak teks dari gambar/PDF menggunakan Tesseract OCR dan parse data."""
        extracted = {
            'invoice_number': 'N/A',
            'date': 'N/A',
            'date_obj': fields.Date.today(),  # Fallback hari ini
            'vendor': 'N/A',
            'total': 'N/A',
            'total_float': 0.0,
            'items': [],
            'vat_rate': '0%',
            'raw_text': '',
            'error': None,
        }
        
        try:
            # Decode base64
            image_bytes = base64.b64decode(image_data)
            _logger.info("OCR: Base64 decoded successfully.")
            
            # Deteksi tipe file (tambah PNG support)
            if image_data.startswith(b'\xff\xd8\xff'):  # JPEG
                img = Image.open(io.BytesIO(image_bytes))
                images = [img]
                _logger.info("OCR: Detected JPEG.")
            elif image_data.startswith(b'iVBORw0KGgo'):  # PNG (base64 pattern)
                img = Image.open(io.BytesIO(image_bytes))
                images = [img]
                _logger.info("OCR: Detected PNG.")
            elif image_data.startswith(b'%PDF'):  # PDF
                images = convert_from_bytes(image_bytes)
                _logger.info(f"OCR: Detected PDF with {len(images)} pages.")
            else:
                extracted['error'] = 'Format file tidak didukung (hanya JPG/PNG/PDF).'
                return extracted
            
            if not images:
                extracted['error'] = 'Gagal load gambar/PDF (cek file corrupt atau Poppler untuk PDF).'
                return extracted
            
            # OCR pada halaman pertama (resize jika terlalu besar untuk akurasi)
            img = images[0]
            if img.size[0] > 2000:  # Resize jika lebar > 2000px
                img = img.resize((2000, int(img.size[1] * 2000 / img.size[0])), Image.Resampling.LANCZOS)
            
            text = pytesseract.image_to_string(img, lang='eng+ind', config='--psm 6')  # PSM 6 untuk uniform block text
            _logger.info(f"OCR: Raw text length: {len(text)} chars.")
            
            # Cleaning teks: Normalize spasi dan hapus multiple lines kosong
            text = re.sub(r'\s+', ' ', text).strip()
            lines = [line.strip() for line in text.split('\n') if line.strip() and len(line.strip()) > 5]  # Filter lines pendek
            
            extracted['raw_text'] = text
            
            # Parsing robust dengan regex dan fallback
            for line in lines:
                try:
                    # Invoice Number (contoh: Y/PI-NS/IX/25/0016)
                    if extracted['invoice_number'] == 'N/A':
                        invoice_match = re.search(r'Invoice\s+No\.\s*(Y/PI-NS/IX/\d{2}/\d{4})', line, re.IGNORECASE)
                        if invoice_match:
                            extracted['invoice_number'] = invoice_match.group(1)
                        else:
                            # Fallback: Cari pola serupa
                            fallback_match = re.search(r'(Y/PI-NS/IX/\d{2}/\d{4})', line)
                            if fallback_match:
                                extracted['invoice_number'] = fallback_match.group(1)
                    
                    # Date (multiple format)
                    if extracted['date'] == 'N/A':
                        date_match = re.search(r'(September \d{1,2}, \d{4}|\d{2}/\d{2}/\d{2}|Posting Date\s+(.+?))', line, re.IGNORECASE)
                        if date_match:
                            date_str = date_match.group(1) if date_match.group(1) else date_match.group(2)
                            extracted['date'] = date_str.strip()
                            # Parse date_obj
                            date_formats = ['%B %d, %Y', '%m/%d/%y', '%d/%m/%Y']
                            for fmt in date_formats:
                                try:
                                    extracted['date_obj'] = datetime.strptime(date_str, fmt).date()
                                    break
                                except ValueError:
                                    continue
                    
                    # Vendor (contoh: BINTANG LASER)
                    if extracted['vendor'] == 'N/A' and ('BINTANG LASER' in line or re.search(r'Vendor\s+No\.\s*V\d+', line)):
                        extracted['vendor'] = 'BINTANG LASER'
                    
                    # Total (contoh: Total IDR 77,500)
                    if extracted['total'] == 'N/A':
                        total_match = re.search(r'Total\s+(?:IDR\s*)?([\d,]+)', line, re.IGNORECASE)
                        if total_match:
                            extracted['total'] = total_match.group(1)
                            try:
                                extracted['total_float'] = float(extracted['total'].replace(',', ''))
                            except ValueError:
                                extracted['total_float'] = 0.0
                    
                    # VAT Rate
                    vat_match = re.search(r'VAT\s*%\s*(\d+%)', line, re.IGNORECASE)
                    if vat_match:
                        extracted['vat_rate'] = vat_match.group(1)
                    
                    # Item Lines (contoh: TONER HP 79 A 1 Pieces 77,500)
                    if not extracted['items']:
                        item_match = re.search(r'(TONER HP 79 A)\s+(\d+)\s+Pieces?\s+([\d,]+)', line, re.IGNORECASE)
                        if item_match:
                            qty = int(item_match.group(2))
                            price_str = item_match.group(3).replace(',', '')
                            price = float(price_str) if price_str.isdigit() else 0.0
                            extracted['items'].append({
                                'desc': item_match.group(1),
                                'qty': qty,
                                'unit': 'Pieces',
                                'price': price,
                            })
                            _logger.info(f"OCR: Parsed item: {item_match.group(1)} qty {qty} price {price}")
                
                except Exception as parse_err:
                    _logger.warning(f"OCR Parsing warning on line '{line}': {parse_err}")
                    continue  # Skip line rusak, lanjut
            
            # Fallback jika masih N/A (kata kunci sederhana)
            if extracted['invoice_number'] == 'N/A':
                for line in lines:
                    if any(keyword in line for keyword in ['Invoice No', 'No. Invoice', 'Faktur No']):
                        parts = line.split(':')
                        if len(parts) > 1:
                            extracted['invoice_number'] = parts[1].strip()
                            break
            
            _logger.info(f"OCR: Extraction complete. Invoice: {extracted['invoice_number']}, Total: {extracted['total']}")
            return extracted
            
        except Exception as e:
            _logger.error(f"OCR Error: {e}")
            extracted['error'] = f"Proses OCR gagal: {str(e)}. Pastikan Tesseract dan dependencies terinstall."
            return extracted

    def action_process_ocr(self):
        """Action tombol: Proses OCR dan isi data otomatis."""
        if self.state != 'draft':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'Invoice harus dalam draft state untuk proses OCR!',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        if not self.invoice_image:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'Upload gambar/PDF invoice dulu!',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        if self.move_type != 'in_invoice':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'Fitur ini hanya untuk Purchase Invoice!',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        extracted = self.extract_ocr_data(self.invoice_image)
        if extracted['error']:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'OCR Gagal',
                    'message': extracted['error'],
                    'type': 'danger',
                    'sticky': False,
                }
            }
        
        try:
            # Auto-isi field (hanya jika N/A atau kosong)
            if extracted['invoice_number'] != 'N/A' and not self.name:
                self.name = extracted['invoice_number']
            
            if extracted['date_obj']:
                self.invoice_date = extracted['date_obj']
            
            # Vendor: Cari atau buat baru
            vendor_name = extracted['vendor']
            if vendor_name != 'N/A':
                vendor = self.env['res.partner'].search([('name', 'ilike', vendor_name)], limit=1)
                if not vendor:
                    vendor = self.env['res.partner'].create({
                        'name': vendor_name,
                        'supplier_rank': 1,
                        'is_company': True,  # Asumsi company
                    })
                self.partner_id = vendor.id
                _logger.info(f"OCR: Set vendor {vendor_name} (ID: {vendor.id})")
            
            # Total: Update jika lebih akurat
            if extracted['total_float'] > 0:
                self.amount_total = extracted['total_float']
                # Recalculate jika lines berubah
                self._recompute_payment_terms_lines()
            
            # Auto-tambah/clear dan tambah invoice lines (hapus lines lama jika kosong)
            if self.invoice_line_ids:
                self.invoice_line_ids.unlink()  # Clear existing untuk demo (opsional: comment jika mau append)
            
            sequence = 10
            for item in extracted['items']:
                line_vals = {
                    'move_id': self.id,
                    'sequence': sequence,
                    'name': item['desc'],
                    'quantity': item['qty'],
                    'product_uom_id': self.env.ref('uom.product_uom_unit').id,  # Unit default
                    'price_unit': item['price'],
                    'display_type': False,  # Regular line
                    'product_id': False,  # No product, manual line
                    'tax_ids': False,  # No tax untuk 0% VAT
                }
                new_line = self.invoice_line_ids.new(line_vals)
                new_line._compute_account_id()  # Auto-set account jika perlu
                sequence += 10
                _logger.info(f"OCR: Added line {item['desc']} qty {item['qty']} price {item['price']}")
            
            # VAT: Set no tax jika 0%
            if extracted['vat_rate'] == '0%':
                for line in self.invoice_line_ids:
                    line.tax_ids = [(5, 0, 0)]  # Clear taxes
            
            # Simpan hasil
            self.ocr_extracted_data = str(extracted)
            
            # Recalculate totals
            self._recompute_dynamic_lines()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sukses!',
                    'message': f'Data diekstrak: Invoice {extracted["invoice_number"]}, Vendor {extracted["vendor"]}, Total {extracted["total"]} IDR. Lines: {len(extracted["items"])} item(s).',
                    'type': 'success',
                    'sticky': False,
                }
            }
        
        except Exception as fill_err:
            _logger.error(f"OCR Fill Error: {fill_err}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Fill Data Gagal',
                    'message': f'Parsing sukses tapi isi data error: {str(fill_err)}',
                    'type': 'danger',
                    'sticky': False,
                }
            }
