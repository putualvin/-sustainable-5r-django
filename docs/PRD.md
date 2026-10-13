# PRD — Sustainable 5R

Status: kebutuhan inti disepakati dalam percakapan, diimplementasikan sebagai versi awal untuk UAT. Keputusan terbuka tercantum di bawah. Tanggal: 13 Oktober 2026.

## Tujuan

Memudahkan audit bulanan dan tindak lanjut 5R dengan bukti foto yang mudah dibandingkan, riwayat temuan berulang, dan tanggung jawab yang jelas. Tampilan bersih berorientasi tabel/foto untuk desktop, kartu dan tab untuk HP.

## Pengguna dan hak akses

| Peran | Tanggung jawab |
|---|---|
| Auditee | Menindaklanjuti temuan pada area/PIC miliknya; mengajukan CAPA dan foto perbaikan |
| Auditor | Mencatat audit yang ditugaskan, meninjau bulan sebelumnya, mengirim hasil; tidak menetapkan prioritas/hasil CAPA |
| Komite Unit | Mengatur penugasan, memilih pemeriksaan wajib, menetapkan prioritas, memverifikasi CAPA, menerima eskalasi red tag |
| Red Tag Coordinator | Mengelola barang red tag dan keputusan pengembaliannya, pemindahan, atau pembuangan |
| Manajemen | Membaca ringkasan dan laporan; bukan penerima eskalasi operasional red tag |

Akses dibatasi per unit dan penugasan/PIC. Auditor tidak mengaudit area tempat dirinya menjadi PIC. Admin teknis Django mengelola master data dan akun, bukan peran bisnis keenam.

## Audit bulanan dan temuan berulang

- Satu audit per area per bulan. Auditor selalu mendapat panel temuan dari audit terkirim bulan kalender sebelumnya saat mengaudit.
- Target minimal 20 temuan baru. Temuan berulang tidak mengurangi target temuan baru. Angka “20+1” berarti 20 ditambah pemeriksaan berulang yang dapat lebih dari satu.
- Komite memilih temuan lama yang wajib diperiksa ulang. Semua temuan lama tetap terlihat; pilihan wajib menghalangi pengiriman bila belum ditandai.
- Auditor menentukan **Masih ada** atau **Sudah tidak ada**, disertai bukti foto terkini dan catatan. Masih ada membuat temuan periode kini yang terhubung ke sumber sebelumnya.
- Temuan baru berisi foto, kategori/pertanyaan panduan 5R, lokasi, dan deskripsi. Prioritas ditentukan Komite setelah audit dikirim.
- Audit dapat diedit selama draf, lalu dikunci setelah pengiriman. Riwayat aktivitas mencatat perubahan penting.
- Jika belum ada audit terkirim bulan sebelumnya, tampilkan keadaan kosong yang jelas; jangan membuat temuan berulang fiktif.

## Tindak lanjut

Komite menetapkan Low/High. Auditee mengisi akar masalah, tindakan koreksi, pencegahan, target, foto, dan referensi WO/SC/PO. Komite menilai Done, Progress, atau No Progress dengan catatan. Progress memerlukan WO/SC/PO; Done memerlukan tindakan koreksi dan foto. Penilaian mengunci pengajuan periode tersebut.

## Red tag

Barang memiliki foto, alasan, lokasi, dan tanggal pemasangan. Tenggat adalah tanggal pemasangan +90 hari kalender. Barang yang masih terbuka setelah tenggat dieskalasikan ke Komite Unit melalui aktivitas dan status keterlambatan. Scheduler harian menjalankan eskalasi. Coordinator mencatat keputusan penyelesaian; Manajemen tidak memiliki kotak tugas red tag.

## Laporan

Tabel temuan dan foto sebelum/sesudah, pencarian/filter, ringkasan status, CSV dan tampilan cetak. Formula acuan aplikasi lama: Done +2, Progress +1, No Progress -1 terhadap maksimum 2 poin per temuan dinilai. Penilaian yang belum tersedia ditampilkan sebagai pending, tidak diam-diam dianggap No Progress. Skor akhir dengan penalti Parking Lot belum ditetapkan.

## Offline

Unduh audit draf dan foto referensi terlebih dahulu. Simpan temuan/foto/pemeriksaan secara eksplisit di perangkat. Antrean dikirim dengan ID unik dan akun yang sama; konflik versi tidak boleh menimpa perubahan server tanpa tindakan pengguna. Finalisasi audit tetap online. Penyimpanan offline bukan backup permanen dan tidak melakukan sinkronisasi ketika browser tertutup.

## Kriteria penerimaan utama

1. Auditor dapat membandingkan bulan sebelumnya sambil menambah temuan; HP menyediakan tab untuk kedua tampilan.
2. Audit dengan kurang dari 20 temuan baru atau pemeriksaan wajib belum selesai tidak dapat dikirim.
3. Lebih dari satu temuan berulang dapat terhubung ke temuan sumber dan tidak dihitung sebagai temuan baru.
4. Pengguna unit lain tidak bisa membaca foto/temuan atau mengubah data di luar kewenangannya.
5. Retry operasi offline tidak menggandakan data; perubahan versi ditolak dengan konflik yang dapat ditinjau.
6. Red tag belum selesai lewat 90 hari masuk ke Komite, bukan Manajemen; scheduler ulang tidak menggandakan eskalasi.
7. Layout tabel/foto tetap dapat digunakan pada layar HP.

## Belum termasuk / perlu keputusan

Modul checklist, SSO, pesan email/WhatsApp, migrasi histori, deployment produksi, serta pengujian perangkat HP fisik belum termasuk. Penalti Parking Lot, batas 25 CAPA, cutoff 17.00, dan kebijakan membuka kembali audit/penilaian perlu keputusan lebih lanjut. Tidak ada aturan tersebut yang diam-diam diasumsikan final.
