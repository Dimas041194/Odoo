ERP Employee Import
===================

Overview
--------

Modul ini menambahkan fitur untuk melakukan import data karyawan dari
file Excel (``.xlsx``) ke Odoo 18 Community secara asynchronous
(melalui background job). Fitur ini dirancang untuk menangani file
berisi ribuan baris tanpa membuat antarmuka pengguna menjadi lambat
serta menyediakan logging dan notifikasi email hasil import.

Main Features
-------------

* Import karyawan dari file Excel (format ``.xlsx``).
* Proses import dijalankan sebagai background job (asynchronous)
  menggunakan scheduled action (cron).
* Validasi data per baris (misalnya kolom wajib, deteksi duplikasi
  berdasarkan ``work_email``).
* Logging detail hasil proses (total baris, jumlah sukses, jumlah gagal,
  dan log per baris).
* Notifikasi email hasil import ke pengguna pengaju (opsional, jika
  mail server dikonfigurasi).

Module Structure
----------------

* Nama modul teknis: ``erp_employee_import``
* Dependensi utama:
  
  * ``hr`` – pengelolaan data karyawan.
  * ``mail`` – pengiriman email notifikasi.

* Struktur folder utama:

  * ``models/``

    * ``employee_import.py`` – definisi wizard dan model job.

  * ``views/``

    * ``employee_import_views.xml`` – form wizard dan menu
      *Employee Import*.

  * ``data/``

    * ``cron_employee_import.xml`` – scheduled action untuk
      memproses job pending.
    * ``mail_template_employee_import.xml`` – template email hasil
      import.

  * ``security/``

    * ``ir.model.access.csv`` – hak akses untuk model
      ``hr.employee.import.job``.

Models and Business Logic
-------------------------

* ``hr.employee.import.wizard`` (TransientModel)

  * Field utama: ``file_data`` (Binary), ``filename`` (Char).
  * Tugas:

    * Menerima upload file Excel dari pengguna.
    * Melakukan validasi dasar (file terisi, ekstensi ``.xlsx``,
      ketersediaan library ``openpyxl``).
    * Membuat satu record ``hr.employee.import.job`` dengan
      status ``pending`` dan menyimpan file dalam bentuk binary.
    * Menutup wizard setelah job dibuat sehingga pengguna tidak
      menunggu proses di layar.

* ``hr.employee.import.job`` (Model biasa)

  * Field utama: ``state``, ``user_id``, ``file_data``, ``filename``,
    ``total_rows``, ``success_count``, ``failed_count``, ``log``.
  * Tugas:

    * Menyimpan antrian job import.
    * Menyimpan ringkasan hasil proses dan log per baris.
    * Menyediakan method ``action_process()`` yang akan dipanggil
      oleh cron untuk mengeksekusi import.

Asynchronous Processing
-----------------------

* Sebuah scheduled action pada model ``ir.cron`` didefinisikan di
  ``cron_employee_import.xml``.
* Cron berjalan secara periodik (misalnya setiap 1 menit) dan
  menjalankan kode:

  * mencari job dengan ``state = 'pending'`` (dengan batas jumlah
    tertentu, misalnya 10 job),
  * memanggil method ``action_process()`` pada setiap job tersebut.

* Proses berat (membaca file, looping baris, membuat karyawan) dijalankan
  di ``action_process()``, bukan di wizard, sehingga antarmuka pengguna
  tetap responsif walaupun file berisi banyak baris.

Import Workflow and Validation
------------------------------

* File ``.xlsx`` didekode dari nilai binary, lalu dibaca menggunakan
  library ``openpyxl`` dalam mode *read only*.
* Baris pertama dianggap sebagai header dan dipetakan ke nama kolom,
  minimal:

  * ``name`` (wajib),
  * ``work_email`` (opsional),
  * ``work_phone`` (opsional),
  * ``job_title`` (opsional).

* Untuk setiap baris data:

  * Sistem memastikan kolom ``name`` terisi.
  * Jika ``work_email`` tersedia, sistem mengecek duplikasi karyawan
    berdasarkan email tersebut.
  * Jika valid, sistem membuat record ``hr.employee`` menggunakan
    ``sudo()`` dengan nilai yang sudah dibersihkan.
  * Jika terjadi kesalahan (misalnya data tidak valid atau duplikat),
    baris tersebut tidak menggagalkan keseluruhan job; baris ditandai
    sebagai gagal dan pesan error dicatat di field ``log`` dan juga
    pada server log melalui ``_logger.error()``.

* Setelah seluruh baris diproses, job akan meng‐update:

  * ``state`` menjadi ``done`` atau ``failed``,
  * ``total_rows``, ``success_count``, dan ``failed_count``,
  * isi ``log`` berisi ringkasan per baris.

Logging and Error Handling
--------------------------

* Modul menggunakan kombinasi:

  * Field ``log`` pada model job untuk menyimpan ringkasan hasil yang
    mudah dibaca dari antarmuka Odoo.
  * Fungsi logging Python (``_logger.info()`` dan ``_logger.error()``)
    untuk mencatat status eksekusi dan error teknis di log server.

* Pendekatan ini memudahkan administrator melakukan troubleshooting,
  terutama ketika file berisi data yang tidak konsisten.

Email Notification
------------------

* Modul menyertakan template email
  ``mail_employee_import_result`` pada model
  ``hr.employee.import.job``.
* Setelah proses import selesai, method ``action_process()`` akan:

  * mencari template tersebut menggunakan referensi teknis,
  * bila ditemukan, mengirim email ke pengguna yang tercatat di
    field ``user_id`` pada job.

* Isi email meliputi:

  * ID job import,
  * total baris yang diproses,
  * jumlah baris sukses dan gagal,
  * ringkasan log yang berguna sebagai laporan hasil import.

Configuration
-------------

* Pastikan dependensi modul ``hr`` dan ``mail`` sudah terpasang.
* Pastikan library Python ``openpyxl`` terinstal pada environment
  Odoo.
* Konfigurasikan outgoing mail server agar notifikasi email dapat
  dikirim.
* Aktifkan scheduled action *Employee Import Job Processor* dari
  menu *Settings → Technical → Automation → Scheduled Actions*
  bila diperlukan.

Usage
-----

1. Buka menu *Employees* di Odoo.
2. Pilih menu *Employee Import*.
3. Upload file Excel (``.xlsx``) dengan header minimal:
   ``name``, dan opsional ``work_email``, ``work_phone``, ``job_title``.
4. Klik tombol *Import*. Wizard akan menutup, dan job baru dengan
   status ``pending`` akan dibuat.
5. Tunggu sampai cron mengeksekusi job. Status dan log dapat dicek
   melalui daftar ``hr.employee.import.job`` atau melalui email
   notifikasi yang dikirim ke pengguna.
