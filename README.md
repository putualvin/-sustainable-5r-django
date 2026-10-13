# Sustainable 5R — Django

Aplikasi audit 5R dengan tampilan tabel dan foto, responsif untuk desktop dan HP. Backend Django, template HTML/CSS, dan JavaScript untuk interaksi serta penyimpanan audit offline. Versi awal yang dapat dijalankan dan ditinjau; belum dideploy ke hosting produksi.

## Jalankan lokal (Windows PowerShell)

Memerlukan Python 3.12 atau lebih baru dan Git. Nama repository diawali tanda `-`.

```powershell
git clone https://github.com/putualvin/-sustainable-5r-django.git sustainable-5r-django
cd sustainable-5r-django
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Buka http://127.0.0.1:8000 dan pilih salah satu dari lima peran demo. Data nama, unit, jadwal, CAPA, dan red tag merupakan demonstrasi. Akun demo tidak memiliki password yang dapat digunakan login biasa. Tombol demo hanya tersedia saat `DJANGO_DEBUG=true` dan `DEMO_MODE=true`; jangan gunakan mode ini pada server yang dapat diakses publik.

Pada Linux/macOS, gunakan `.venv/bin/python` sebagai pengganti `.\.venv\Scripts\python.exe`.

## Alur yang tersedia

1. **Komite Unit:** membuat jadwal, memilih beberapa temuan bulan sebelumnya yang wajib diperiksa ulang, menetapkan prioritas, menilai tindak lanjut.
2. **Auditor:** membuka audit, melihat temuan bulan sebelumnya sambil bekerja, menandai kondisi masih ada/sudah tidak ada dengan foto terbaru; menambah dan mengedit temuan baru sebelum mengirim audit.
3. **Auditee:** mengisi akar masalah, koreksi, pencegahan, target, WO/SC/PO, dan foto perbaikan.
4. **Red Tag Coordinator:** memantau barang berlabel dan menetapkan penyelesaian. Batas 90 hari dihitung dari pemasangan; keterlambatan masuk ke Komite Unit.
5. **Manajemen:** melihat ringkasan dan laporan; tidak menangani eskalasi red tag.

Audit memerlukan minimal 20 temuan baru dan seluruh pemeriksaan ulang wajib selesai. Temuan berulang tercatat terpisah dan boleh lebih dari satu. Pertanyaan panduan mengelompokkan temuan dalam 5R; bukan modul checklist.

## Mencoba offline

- Login sebagai Auditor, buka audit draf, klik **Siapkan offline** saat terhubung.
- Buka **ruang audit offline**. Referensi bulan sebelumnya dan foto disimpan di IndexedDB perangkat.
- Simpan temuan baru atau pemeriksaan ulang dengan tombol **Simpan di perangkat**. Isian yang belum disimpan belum masuk antrean.
- Saat koneksi kembali, klik **Sinkronkan sekarang** dengan akun yang sama. Pengiriman menggunakan ID operasi unik agar retry tidak menggandakan temuan; konflik pemeriksaan perlu ditinjau pengguna.
- Pengiriman audit final dilakukan online. Sinkronisasi berjalan ketika halaman aktif, bukan layanan latar belakang saat browser tertutup.

Offline memerlukan HTTPS atau localhost. Gunakan perangkat pribadi: data unduhan tersimpan di browser dan dapat dibaca offline oleh pemegang perangkat. Logout membersihkan penyimpanan lokal dan memberi konfirmasi bila masih ada antrean. Penghapusan data browser dapat menghapus draf yang belum disinkronkan. Unduh ulang referensi setelah Komite mengubah pilihan wajib atau data audit berubah.

## Pemeriksaan

```powershell
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
```

Pengujian mencakup akses antarperan/unit, syarat pengiriman audit, riwayat berulang, konflik dan duplikasi sinkronisasi, bukti foto, penilaian CAPA, edit draf, serta eskalasi red tag. GitHub Actions menjalankan pengujian otomatis.

## Persiapan produksi

Contoh variabel ada di `.env.example`; aplikasi membaca environment proses, **tidak otomatis membaca file `.env`**. Set variabel melalui platform hosting atau PowerShell sebelum menjalankan perintah.

- Set `DJANGO_DEBUG=false`, `DEMO_MODE=false`, secret acak, host, serta origin HTTPS yang benar.
- Gunakan PostgreSQL melalui `DATABASE_URL`; SQLite hanya untuk pengembangan sederhana. Integrasi PostgreSQL perlu diuji di lingkungan tujuan.
- Jalankan migrasi dan `collectstatic`, buat superuser dengan `manage.py createsuperuser`. Kelola Unit, Area/PIC, Membership, pertanyaan, serta pengguna melalui `/admin/`. Keanggotaan per unit menentukan akses aplikasi.
- Jalankan WSGI, misalnya `.venv\Scripts\waitress-serve.exe --listen=127.0.0.1:8000 config.wsgi:application`, di belakang HTTPS reverse proxy. Konfigurasikan trusted proxy HTTPS secara benar di infrastruktur; jangan mempercayai header yang dapat dikirim langsung oleh publik.
- Simpan database dan `media/` secara persisten, buat backup dan uji pemulihan. Foto bukti dilayani melalui pemeriksaan izin; jangan mengekspos `media/` sebagai direktori publik.
- Jadwalkan `python manage.py escalate_redtags` **setiap hari** dengan scheduler hosting/Task Scheduler. Perintah idempotent; tanpa scheduler, eskalasi tidak berjalan otomatis.
- Tambahkan rate limiting login, logging/monitoring, kebijakan retensi, serta uji penerimaan pengguna sebelum operasional.

## Batas versi awal dan keputusan terbuka

- Laporan menampilkan hasil penilaian utama dan jumlah berulang. Penalti Parking Lot belum disepakati, sehingga skor akhir gabungan belum diterbitkan.
- Aturan lama tentang maksimum 25 CAPA dan batas waktu pukul 17.00 belum diterapkan; perlu konfirmasi apakah masih berlaku.
- Belum ada notifikasi email/WhatsApp, SSO, impor data historis, atau deployment hosting.
- Foto demo ilustratif digunakan ulang, termasuk perbandingan sebelum/sesudah. Foto berasal dari aset repository aplikasi 5R milik pengguna (`putualvin/sustainable-5r-shadow`); jangan menganggapnya bukti audit nyata. Tidak ada lisensi redistribusi terpisah yang ditetapkan oleh proyek ini.

Rincian kebutuhan dan kriteria penerimaan: [docs/PRD.md](docs/PRD.md).
