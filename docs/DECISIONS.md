# Dokumentasi Keputusan Teknis & Arsitektur (DECISIONS.md)

Dokumen ini mencatat seluruh keputusan arsitektur dan bisnis yang menjadi pedoman dalam pembangunan sistem backend RetailBrain, mengacu pada Bab 1.3 Blueprint serta penyelesaian aspek teknis selama fase implementasi.

---

## 1. Keputusan Utama Blueprint (D1 - D8)

### D1: Representasi Nilai Keuangan (Integer Rupiah)
- **Keputusan**: Semua nilai uang (`price`, `subtotal`, `discount`, `delivery_fee`, `total`, `value` voucher) disimpan dan dihitung dalam tipe data **Integer Rupiah**, bukan tipe data desimal/float.
- **Rasional**: Menghindari galat pembulatan presisi aritmatika floating point IEEE 754 (mis. `0.1 + 0.2 != 0.3`).
- **Aturan Pembulatan Diskon**: Pada voucher bertipe persentase, hasil potongan dibulatkan ke bawah (*floor*) ke satuan Rupiah terdekat: `int(subtotal * percent / 100)`.

### D2: Zona Waktu dan Format Datetime
- **Keputusan**: Seluruh stempel waktu (`created_at`, `updated_at`, `starts_at`, `ends_at`, `at`) disimpan dalam basis data sebagai objek UTC Date (`datetime.now(timezone.utc)`).
- **Rasional**: Mencegah inkonsistensi zona waktu saat server atau replika basis data berada di wilayah geografis berbeda.
- **Penyajian**: Pada layer presentasi (UI) dan pengelompokan agregasi penjualan harian, waktu dikonversi ke zona waktu Indonesia Barat (`Asia/Jakarta` / UTC+7).

### D3: Konsistensi Transaksi Pembatalan Order (Cancellation Lifecycle)
- **Keputusan**: Pembatalan pesanan pada seluruh status yang diizinkan (`pending`, `confirmed`, `processing`, `ready_for_pickup`) secara konsisten mengeksekusi:
  1. Pemulihan stok di `master_product` (`$inc: {stock: qty}`).
  2. Pencatatan record `stock_movements` bertipe `restoration` (+qty) dengan invarian `after = before + qty`.
  3. Pengembalian kuota voucher jika order menggunakan voucher (`$inc: {used_count: -1}`).
  4. Penyesuaian `payment_status`: jika `paid` $\to$ `refunded`, jika `awaiting_verification` $\to$ `failed`, jika `unpaid` tetap `unpaid`.
  5. Pencatatan ke `status_history` dan `audit_logs`.
- **Rasional**: Memastikan konsistensi penuh inventori dan hak promosi pelanggan terlepas dari tahap pemrosesan saat pembatalan terjadi.

### D4: Soft Delete pada Penghapusan Produk
- **Keputusan**: Aksi `DELETE /admin/products/<id>` tidak menghapus dokumen secara fisik dari MongoDB, melainkan menetapkan flag `is_active = False`.
- **Rasional**: Menjaga integritas data referensial dan riwayat transaksi masa lalu pada koleksi `orders` dan `stock_movements`. Produk nonaktif otomatis disaring keluar dari katalog publik dan pencarian.

### D5: Format Nomor Order Tanpa Koleksi Counter
- **Keputusan**: Nomor pesanan diformat sebagai `RB-YYYYMMDD-NNNNNN` (menggunakan modul `secrets` untuk 6 digit acak yang aman secara kriptografi). Jika terjadi benturan unik (`DuplicateKeyError`), sistem melakukan retry otomatis hingga 3 kali.
- **Rasional**: Mencegah pembuatan koleksi ke-12 (aturan ketat: tepat 11 koleksi) dan menghindari *lock contention* yang biasa timbul pada dokumen counter sekuensial.

### D6: Penyajian Bukti Transfer Melalui Rute Terautentikasi
- **Keputusan**: Berkas bukti transfer tidak disimpan di folder statis publik `/static` atau dilayani langsung via web server publik tanpa proteksi. Disediakan endpoint terproteksi `GET /orders/<id>/payment-proof`.
- **Rasional**: Melindungi privasi keuangan pelanggan. Hanya pemilik sah order tersebut dan pengguna dengan role `admin` yang diizinkan mengunduh atau melihat bukti transfer (TC-SC-06). Akses oleh pengguna lain menghasilkan respons HTTP 404/403.

### D7: Isolasi Pustaka PyMongo pada Layer Repositori
- **Keputusan**: Mengimpor modul `pymongo` hanya diperkenankan di dalam folder `app/repositories/`. Layer `routes`, `services`, `utils`, dan `templates` sama sekali tidak boleh mengimpor `pymongo`.
- **Rasional**: Menerapkan arsitektur bersih 6-layer sejati (*Clean Architecture*). Jika suatu saat pustaka basis data diperbarui atau diganti, perubahan terisolasi hanya pada repositori tanpa merusak logika bisnis di service.

### D8: Pemisahan Ketat Hak Akses Pelanggan dan Admin
- **Keputusan**: Pengguna dengan role `admin` dilarang melakukan transaksi belanja pelanggan (`/cart`, `/checkout`, `/wishlist`) dan akan mendapatkan respons HTTP 403 Forbidden via decorator `@customer_only`.
- **Rasional**: Menegakkan pemisahan tugas (*Separation of Duties*) dan integritas data audit. Akun admin difokuskan untuk tata kelola operasional toko.

---

## 2. Keputusan Teknis Implementasi Tambahan

### D9: Transaksi Multi-Dokumen MongoDB dengan Fallback Kompensasi
- **Keputusan**: Sistem mendeteksi otomatis ketersediaan MongoDB Replica Set saat aplikasi berjalan. Jika replica set aktif, sistem menjalankan transaksi multi-dokumen native (`with client.start_session() as s: with s.start_transaction():`). Jika dijalankan pada standalone MongoDB tanpa replica set, sistem mengeksekusi operasi dengan mekanisme kompensasi otomatis (*saga pattern / compensation steps*) pada blok `try...except`.
- **Rasional**: Menjamin portabilitas penuh. Aplikasi dapat dijalankan dengan aman baik di lingkungan Docker lokal, klaster MongoDB Atlas replica set, maupun standalone development tanpa membuat sistem crash.

### D10: Validasi dan Rekomputasi Sisi Server (Zero Client Trust)
- **Keputusan**: Nilai harga produk, subtotal keranjang, diskon voucher, dan ongkos kirim tidak pernah dipercayai dari input klien (form/JSON).
- **Rasional**: Menangkal serangan *parameter tampering*. Server selalu membaca harga produk resmi langsung dari `master_product` dan menghitung ulang seluruh nilai secara mandiri sebelum transaksi dieksekusi.

### D11: Penanganan Unggah Gambar Aman (Defense in Depth)
- **Keputusan**: Unggah foto produk dan bukti transfer menerapkan validasi 4 lapis:
  1. Pemeriksaan ekstensi nama berkas (hanya `.jpg`, `.jpeg`, `.png`).
  2. Pemeriksaan batas ukuran berkas maksimum 2 MB.
  3. *Image Decoding & Verification* menggunakan pustaka Pillow (`Image.open().verify()`) untuk mendeteksi berkas biner berbahaya / shell script yang menyamar sebagai gambar.
  4. Penyimpanan menggunakan nama berkas acak UUID v4 (`<uuid>.jpg` / `<uuid>.png`) untuk mencegah *path traversal attacks* (`../../`).

