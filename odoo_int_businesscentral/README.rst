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

Nilai integrasi BC disimpan
