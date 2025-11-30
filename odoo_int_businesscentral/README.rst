BC Purchase Invoice Integration
===============================

Overview
--------

Modul ini menambahkan integrasi antara Odoo 18 dan Microsoft Dynamics 365
Business Central (BC) untuk mengirim purchase invoice dari Odoo ke BC.
Integrasi mencakup pembuatan header invoice di BC, pengiriman lines
(invoice lines) dari Odoo, serta penyimpanan nomor invoice BC kembali
ke dalam Odoo sebagai referensi.

Saat ini alur utama yang diimplementasikan bersifat satu arah
(Odoo → BC). Desain modul sudah dipersiapkan agar di tahap berikutnya
dapat diperluas untuk menarik informasi pembayaran dari BC ke Odoo
(pembaruan status invoice dan pembuatan payment secara otomatis).
[web:13]

Features
--------

* Menambahkan field nomor invoice BC pada ``account.move``:
  ``x_bc_invoice_number`` (No. Invoice BC, readonly).
* Mendapatkan dan me-*refresh* access token OAuth2 BC secara otomatis
  dengan mekanisme caching di ``ir.config_parameter``.
* Mengirim header purchase invoice dari Odoo ke BC.
* Mengirim invoice lines terkait ke BC berdasarkan nomor invoice BC
  yang sudah dibuat.
* Tombol satu kali klik untuk mengirim header, menunggu jeda, lalu
  mengirim seluruh lines.
* Pencatatan status dan error melalui ``message_post`` di chatter
  invoice.
* Desain extensible untuk penambahan fitur sinkronisasi pembayaran
  dari BC ke Odoo di masa depan. [web:13]

Technical Design
----------------

Model Extension
~~~~~~~~~~~~~~~

* Model yang di-*extend*: ``account.move``.
* Field tambahan:

  * ``x_bc_invoice_number`` (Char, readonly)
    - Menyimpan nomor invoice yang dikembalikan oleh Business Central.

Configuration Parameters
~~~~~~~~~~~~~~~~~~~~~~~~

Nilai integrasi BC disimpan di ``ir.config_parameter``:

* ``bc_integration.client_id`` – Client ID aplikasi Azure AD.
* ``bc_integration.client_secret`` – Client Secret aplikasi Azure AD.
* ``bc_integration.tenant_id`` – Tenant ID Azure AD.
* ``bc_integration.company_id`` – ID company di Business Central.
* ``bc_integration.access_token`` – Access token yang disimpan sementara.
* ``bc_integration.access_token_expiry`` – Timestamp kadaluarsa token.

Dengan pendekatan ini, token hanya diminta ulang ketika:

* belum tersimpan, atau
* sudah mendekati kadaluarsa (dihitung berdasarkan ``expires_in``).

Access Token Handling
---------------------

* Method ``_get_valid_token()``:

  * Membaca token dan waktu kadaluarsa dari ``ir.config_parameter``.
  * Mengecek waktu saat ini; jika token tidak ada atau hampir kedaluwarsa,
    akan memanggil ``_get_bc_token()`` untuk mengambil token baru.
  * Mengembalikan access token yang valid untuk dipakai di request BC.

* Method ``_get_bc_token()``:

  * Menyusun request OAuth2 *client_credentials* ke endpoint:
    ``https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token``.
  * Mengirim ``client_id``, ``client_secret``, dan ``scope`` standar
    Business Central: ``https://api.businesscentral.dynamics.com/.default``.
  * Jika berhasil, menyimpan ``access_token`` dan ``expiry`` ke
    ``ir.config_parameter`` dan mengembalikannya ke pemanggil.
  * Jika gagal, melempar exception dengan isi response untuk memudahkan
    debugging. [web:13]

Invoice Header Synchronization
------------------------------

* Method: ``action_send_to_bc_purchase_invoice()`` pada ``account.move``.

Alur kerja:

1. Mengambil access token valid melalui ``_get_valid_token()``.
2. Mengambil ``company_id`` dan ``tenant_id`` dari konfigurasi.
3. Menyusun URL endpoint BC, contoh:
   ``https://api.businesscentral.dynamics.com/v2.0/{tenant_id}/Production/ODataV4/Company({company_id})/Purchinv``.
4. Menyusun payload header minimal, misalnya:

   * ``Document_Type`` = ``Invoice``
   * ``Buy_from_Vendor_Name`` = nama vendor dari ``partner_id`` invoice.

5. Mengirim request ``POST`` ke BC dengan header:

   * ``Authorization: Bearer <token>``
   * ``Content-Type: application/json``
   * ``Accept: application/json``

6. Jika berhasil (status 200/201):

   * Membaca body JSON, mengambil nomor invoice BC
     (misalnya key ``No`` atau ``Document_No``).
   * Menyimpan nomor ini ke field ``x_bc_invoice_number``.
   * Menulis pesan sukses di chatter dengan ``message_post()``.

7. Jika gagal:

   * Menulis pesan error lengkap dari response ke chatter invoice.

Invoice Lines Synchronization
-----------------------------

* Method: ``action_send_lines_to_bc()`` pada ``account.move``.

Alur kerja:

1. Mengecek ketersediaan ``x_bc_invoice_number``.
   Jika kosong, menulis pesan error di chatter dan menghentikan proses.
2. Mengambil access token, ``company_id``, dan ``tenant_id``.
3. Menyusun URL endpoint lines, contoh:
   ``https://api.businesscentral.dynamics.com/v2.0/{tenant_id}/Production/ODataV4/Company({company_id})/purchaseInvoiceLines``.
4. Menginisialisasi ``line_number`` (misal 10000) lalu loop
   ``invoice_line_ids``:

   * Jika line tidak memiliki ``product_id``, line dilewati dan
     dibuatkan pesan peringatan di chatter.
   * Menyusun payload:

     * ``Document_Type`` = ``Invoice``
     * ``Document_No`` = ``
