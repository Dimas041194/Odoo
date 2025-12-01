===============================================
Integrasi Purchase Invoice Odoo - BC (REST API)
===============================================

Deskripsi
=========

Modul ini menambahkan integrasi antara Odoo dan Microsoft Dynamics 365 Business Central (BC) untuk dokumen *Vendor Bill / Purchase Invoice* pada model ``account.move``. [web:13]  
Invoice header dan invoice lines dari Odoo akan dikirim ke BC melalui REST API menggunakan mekanisme OAuth2 Client Credentials. [web:3]

Fitur
=====

* Penambahan field baru pada ``account.move``:

  * ``x_bc_invoice_number``: Menyimpan nomor invoice yang dihasilkan dari BC (readonly).

* Manajemen token OAuth2 otomatis:

  * ``_get_valid_token()``: Mengecek token di parameter sistem dan memperbarui jika sudah hampir kedaluwarsa.
  * ``_get_bc_token()``: Meminta token baru ke Azure AD dan menyimpan token beserta waktu kedaluwarsa ke ``ir.config_parameter``. [web:3]

* Pengiriman header purchase invoice ke BC:

  * Method: ``action_send_to_bc_purchase_invoice()``.
  * Mengirim data header seperti ``Document_Type`` dan ``Buy_from_Vendor_Name`` ke endpoint OData BC.
  * Menyimpan nomor invoice BC yang diterima ke ``x_bc_invoice_number`` dan menuliskan log di chatter.

* Pengiriman invoice lines ke BC:

  * Method: ``action_send_lines_to_bc()``.
  * Hanya berjalan jika ``x_bc_invoice_number`` sudah terisi.
  * Mengirim setiap baris ``invoice_line_ids`` sebagai ``purchaseInvoiceLines`` di BC (quantity, unit cost, description, item code, dll.).
  * Baris tanpa ``product_id`` akan dilewati dan dicatat di chatter.

* Tombol utama untuk kirim header + lines:

  * Method: ``action_send_invoice_and_lines()``.
  * Memanggil pembuatan header, menunggu 60 detik, kemudian mengirim lines ke BC.

Instalasi
=========

1. Letakkan modul ini di direktori ``custom-addons`` (atau direktori addons kustom Anda). [web:12]  
2. Pastikan dependency dasar untuk integrasi HTTP (misalnya library ``requests``) sudah tersedia di environment Odoo Anda. [web:15]  
3. Update daftar modul dan instal modul dari Apps di Odoo.

Konfigurasi
===========

Sebelum modul digunakan, set parameter berikut di:

*Settings → Technical → Parameters → System Parameters*

Parameter yang diperlukan:

* ``bc_integration.client_id``  
  Client ID aplikasi di Azure AD.

* ``bc_integration.client_secret``  
  Client Secret aplikasi di Azure AD.

* ``bc_integration.tenant_id``  
  Tenant ID Azure AD (GUID tenant).

* ``bc_integration.company_id``  
  Company ID di Business Central (format GUID yang digunakan di URL OData BC). [web:3]

* ``bc_integration.access_token``  
  Akan diisi otomatis oleh modul ketika token berhasil diambil.

* ``bc_integration.access_token_expiry``  
  Akan diisi otomatis oleh modul (epoch time kadaluarsa token).

Pastikan juga:

* Aplikasi Azure AD telah diberikan permission ke API Business Central dengan scope ``https://api.businesscentral.dynamics.com/.default``. [web:3]  
* Endpoint OData v4 Business Central aktif dan object ``Purchinv`` serta ``purchaseInvoiceLines`` dapat diakses oleh token tersebut.

Penggunaan
==========

1. Buat atau buka *Vendor Bill / Purchase Invoice* di Odoo (model ``account.move`` dengan ``move_type = 'in_invoice'``). [web:6]  
2. Pastikan:

   * Vendor sudah benar.
   * Semua invoice line terisi, termasuk ``product_id`` dan harga satuan.

3. Tekan tombol yang terhubung ke:

   * ``action_send_to_bc_purchase_invoice()`` jika hanya ingin mengirim header, atau
   * ``action_send_invoice_and_lines()`` jika ingin kirim header dan lines sekaligus (otomatis tunggu 60 detik sebelum kirim lines).

4. Cek chatter di form invoice:

   * Jika berhasil, akan muncul pesan sukses dan field ``No. Invoice BC`` terisi dengan nomor invoice BC.
   * Jika gagal, pesan error (response text dari BC) akan tercatat di chatter untuk dianalisis.

5. Setelah invoice berada di BC dan pembayaran dilakukan di BC, integrasi lanjutan dapat dibuat untuk:

   * Mengambil data payment dari BC.
   * Membuat ``account.payment`` di Odoo dan melakukan rekonsiliasi terhadap invoice terkait.

Arsitektur Teknis
=================

* Model yang di-*inherit*: ``account.move``. [web:12]  
* Field tambahan:

  * ``x_bc_invoice_number = fields.Char(string="No. Invoice BC", readonly=True)``

* Pengelolaan Token:

  * Token dan expiry disimpan di ``ir.config_parameter`` untuk menghindari permintaan token berulang yang tidak perlu.
  * Validasi token dilakukan dengan toleransi waktu (buffer 60 detik sebelum expiry).

* Endpoint utama yang digunakan:

  * OAuth2 Token (Azure AD):

    ``https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token``

  * Header Purchase Invoice:

    ``https://api.businesscentral.dynamics.com/v2.0/{tenant_id}/Production/ODataV4/Company({company_id})/Purchinv``

  * Purchase Invoice Lines:

    ``https://api.businesscentral.dynamics.com/v2.0/{tenant_id}/Production/ODataV4/Company({company_id})/purchaseInvoiceLines``

Keterkaitan dengan Proses Pembayaran
====================================

Modul ini terutama menangani pembuatan invoice di Business Central dari data invoice di Odoo. [web:3]  
Dalam skenario validasi pembayaran, setelah pembayaran dilakukan dan tercatat di BC, dapat ditambahkan modul/skrip terpisah untuk:

* Job queue
* Membaca status pembayaran atau ledger entries di BC via API. [web:14]  
* Menghubungkannya ke invoice Odoo berdasarkan ``x_bc_invoice_number`` atau referensi lain.
* Membuat payment dan melakukan rekonsiliasi otomatis di Odoo sesuai kebutuhan bisnis.
* Validasi agar hanya invoice yang sudah *posted* yang bisa dikirim ke BC. [web:6]
* Mekanisme pencegahan pengiriman ganda bila ``x_bc_invoice_number`` sudah terisi.
* Sinkronisasi balik payment dari BC ke Odoo (otomatis membuat ``account.payment`` dan rekonsiliasi).


Lisensi
=======

Modul ini harus menyebutkan lisensi yang digunakan (misalnya AGPL-3, LGPL-3, atau lainnya) di berkas ``__manifest__.py`` sesuai kebijakan proyek Anda. [web:12]

