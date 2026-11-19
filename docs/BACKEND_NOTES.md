# Panduan Teknis & Bahan Presentasi Backend (BACKEND_NOTES.md)

Dokumen ini disusun sebagai panduan komprehensif bagi pengembang untuk memahami, menjelaskan, dan mempresentasikan arsitektur serta logika teknis sistem backend **RetailBrain** di hadapan dosen penguji.

---

## 1. Ringkasan Eksekutif Sistem

**RetailBrain** adalah platform web e-commerce ritel modern yang dibangun menggunakan **Python (Flask)** dan basis data dokumen **MongoDB**. Sistem ini memadukan kemudahan operasional UMKM ritel dengan keandalan enterprise:
- **Tepat 11 Koleksi Basis Data** dengan validasi ketat `$jsonSchema` dan indeks performa.
- **Koleksi Wajib `master_product`** sebagai *single source of truth* untuk seluruh data barang dan inventori.
- **Konsistensi Transaksi Atomik** pada transaksi multi-dokumen saat checkout pesanan.
- **Keamanan Berlapis**: Argon2id hashing, session fixation prevention, CSRF protection, Flask-Limiter, isolasi PyMongo, dan verifikasi berkas gambar aman.

---

## 2. Arsitektur 6-Layer (Clean Architecture)

RetailBrain menerapkan pembagian tanggung jawab yang tegas antar-layer (*Separation of Concerns*). Tidak ada layer yang melompati tanggung jawabnya.

```
┌────────────────────────────────────────────────────────┐
│  1. Presentation Layer (Jinja2 Templates & Static UI) │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTP Request / Form / JSON
┌──────────────────────────▼─────────────────────────────┐
│  2. Route / Blueprint Layer (HTTP Handlers)           │
│     * Validasi format request, tanpa logika bisnis     │
└──────────────────────────┬─────────────────────────────┘
                           │ Cek sesi & token
┌──────────────────────────▼─────────────────────────────┐
│  3. Auth & Authorization Layer (RBAC & Decorators)     │
│     * @login_required, @role_required, @customer_only │
└──────────────────────────┬─────────────────────────────┘
                           │ Panggil fungsionalitas bisnis
┌──────────────────────────▼─────────────────────────────┐
│  4. Service Layer (Business Logic & Transactions)      │
│     * Rekomputasi harga, transaksi atomik, state flow  │
└──────────────────────────┬─────────────────────────────┘
                           │ Operasi basis data
┌──────────────────────────▼─────────────────────────────┐
│  5. Repository Layer (Data Access - Satu-satunya PyMongo)
│     * Eksekusi query MongoDB, isolasi pustaka driver   │
└──────────────────────────┬─────────────────────────────┘
                           │ Driver wire protocol
┌──────────────────────────▼─────────────────────────────┐
│  6. Database Layer (MongoDB 7.0+ Database Engine)      │
│     * 11 Koleksi, $jsonSchema, Indeks Unik & Compound │
└────────────────────────────────────────────────────────┘
```

### Mengapa Isolasi PyMongo Sangat Penting?
Hanya layer `repositories` yang diperkenankan mengimpor `pymongo`. Layer `routes` dan `services` tidak mengetahui detail implementasi driver database. Manfaatnya:
1. **Dapat Diuji dengan Mudah (Testability)**: Service dapat diuji unit tanpa ketergantungan driver langsung.
2. **Kemudahan Migrasi & Perawatan**: Jika pustaka driver mengalami pembaruan API di masa mendatang, perbaikan hanya terkonsentrasi pada kelas repositori.

---

## 3. Penjelasan Logika Teknis Modul Utama

### A. Autentikasi & Pengamanan Sesi
1. **Argon2id Hashing**: Password pengguna di-hash menggunakan algoritma pemenang password hashing competition terkini, **Argon2id**, dengan parameter resisten GPU dan serangan *side-channel*.
2. **Pencegahan Session Fixation**: Saat pengguna berhasil masuk (`login`), sesi lama dibersihkan (`session.clear()`) dan diterbitkan ID sesi baru.
3. **Pesan Galat Generik**: Jika login gagal (baik email tidak terdaftar maupun password salah), sistem mengembalikan pesan identik: *"Email atau password salah"* dengan status HTTP 401. Hal ini mencegah peretas menebak keberadaan email (*user enumeration*).
4. **Keamanan Cookie**: Cookie sesi dikonfigurasi dengan flag `HttpOnly=True` (mencegah pencurian cookie via serangan JavaScript XSS), `SameSite=Lax` (mencegah eksploitasi CSRF pihak ketiga), dan `Secure=True` pada koneksi produksi HTTPS.

---

### B. Keranjang Belanja (Shopping Cart)
- **Persistensi Sisi Server**: Keranjang belanja disimpan di koleksi `carts` berbasis `user_id`. Pelanggan yang login di perangkat berbeda tetap melihat keranjang belanja yang sama.
- **Penggabungan Item**: Jika produk yang sama ditambahkan kembali, kuantitasnya dijumlahkan secara otomatis.
- **Validasi Kuantitas**: Kuantitas dibatasi integer antara 1 hingga 99 unit, dan tidak boleh melebihi sisa stok fisik di `master_product`.

---

### C. Checkout & Pembuatan Order Atomik
- **Pencegahan Submit Ganda (Idempotency Key)**: Setiap kali halaman checkout dibuka, sistem menerbitkan UUID acak sebagai `idempotency_key`. Jika pengguna tidak sengaja mengeklik tombol bayar dua kali atau me-refresh halaman, request kedua mengenali kunci tersebut dan mengembalikan order yang telah dibuat tanpa memotong stok dua kali (TC-CO-07).
- **Rekomputasi Sisi Server (Zero Client Trust)**: Server mengabaikan harga total yang dikirim klien. Server membaca ulang harga satuan produk langsung dari `master_product`, memvalidasi voucher dari `promotions`, dan menghitung ulang subtotal serta total biaya.
- **Transaksi Multi-Dokumen MongoDB**:
  Dalam satu sesi transaksi atomik (`with client.start_session() as s: with s.start_transaction():`):
  1. Stok produk dikurangi bersyarat `{_id: pid, stock: {$gte: qty}}`. Jika stok tiba-tiba habis diperebutkan pengguna lain, transaksi gagal dan di-rollback.
  2. Catatan pengurangan stok dicatat pada `stock_movements` (tipe `reduction`, quantity bertanda negatif).
  3. Kuota voucher dinaikkan secara atomik `{code: vcode, $expr: {$lt: ["$used_count", "$quota"]}}`.
  4. Dokumen order lengkap disimpan (dengan snapshot rincian barang, kontak, alamat, dan stempel status awal).
  5. Keranjang belanja dikosongkan.
  6. Audit log dicatat.

---

### D. Siklus Transisi Status Pesanan & Pembayaran (State Machine)
Order memiliki dua status independen:
1. `order_status`: `pending` $\to$ `confirmed` $\to$ `processing` $\to$ `ready_for_pickup` $\to$ `completed` (atau `cancelled`).
2. `payment_status`: `unpaid` $\to$ `awaiting_verification` $\to$ `paid` (atau `failed` / `refunded`).

**Pembaruan Bersyarat (Optimistic Concurrency Control)**:
Setiap perubahan status dilakukan dengan filter:
```python
{"_id": order_id, "order_status": status_asal}
```
Jika dua admin mengklik tombol bersamaan, hanya satu permintaan yang berhasil mengubah data; permintaan kedua mendeteksi kondisi status tidak cocok dan ditolak dengan status HTTP 409 Conflict (TC-OR-03).

**Aturan Prasyarat Transisi**:
- Masuk ke `processing`: Pada transfer bank, status pembayaran **harus sudah `paid`**. Pada metode COD, diperbolehkan masih `unpaid`.
- Masuk ke `completed`: Pembayaran **harus berstatus `paid`**. Pada pesanan COD, admin harus mencatat uang tunai diterima (`mark_cod_paid`) sebelum menyelesaikan order.
- Dampak status `completed`: Secara otomatis menambah metrik penjualan `sold_count` pada masing-masing produk yang dibeli.

**Alur Pembatalan Pesanan (Cancel)**:
- Pelanggan hanya boleh membatalkan saat pesanan berstatus `pending`.
- Admin dapat membatalkan pesanan pada status `pending`, `confirmed`, `processing`, dan `ready_for_pickup`.
- Pada saat pembatalan, sistem secara atomik memulihkan stok barang, mencatat mutasi `restoration`, mengembalikan kuota voucher, dan mengubah `payment_status` (dari `paid` $\to$ `refunded`, atau dari `awaiting_verification` $\to$ `failed`).

---

### E. Manajemen Inventori & Mutasi Stok (Stock Movements)
- **Tabel Mutasi Append-Only**: Koleksi `stock_movements` mencatat seluruh riwayat mutasi stok (`initial`, `addition`, `reduction`, `correction`, `restoration`). Data riwayat stok tidak pernah diubah atau dihapus (*immutable*).
- **Invarian Wajib**: Pada setiap pencatatan mutasi berlaku rumus:
  $$\text{after\_stock} = \text{before\_stock} + \text{quantity} \quad \text{dan} \quad \text{after\_stock} \ge 0$$
- **Stock Opname (Correction)**: Admin dapat memasukkan hasil hitung fisik barang di toko. Sistem menghitung selisih bertanda ($\pm$), memperbarui master data, dan mewajibkan pengisian catatan alasan opname.
- **Deteksi Stok Rendah (Low-Stock)**: Filter `stock <= min_stock` secara otomatis menampilkan daftar barang yang membutuhkan pemesanan ulang ke supplier.

---

### F. Pelaporan Penjualan & Dashboard Eksekutif
- **Zero Mock Data**: Semua metrik dihitung langsung dari basis data MongoDB menggunakan Aggregation Pipeline.
- **Hanya Order Completed**: Laporan pendapatan dan volume transaksi hanya menghitung pesanan yang berstatus `completed`. Pesanan batal atau yang belum selesai tidak diikutsertakan.
- **Zona Waktu Asia/Jakarta**: Pengelompokan harian menggunakan operator `$dateToString` dengan parameter `timezone: "Asia/Jakarta"`:
  ```json
  {
    "$group": {
      "_id": {
        "$dateToString": {
          "format": "%Y-%m-%d",
          "date": "$created_at",
          "timezone": "Asia/Jakarta"
        }
      },
      "total_sales": { "$sum": "$total" },
      "order_count": { "$sum": 1 }
    }
  }
  ```

---

## 4. Prediksi Pertanyaan Ujian / Sidang & Rekomendasi Jawaban

### Q1: "Mengapa memilih MongoDB dan bagaimana menjamin konsistensi data penjualan bila terjadi gangguan server?"
> **Jawaban**:
> "MongoDB dipilih karena model dokumen JSON sangat selaras dengan domain ritel: produk memiliki spesifikasi dan kategori fleksibel, keranjang belanja dan order memerlukan penyimpanan dokumen bersarang (*nested items snapshot*), serta riwayat mutasi status dapat ditampung langsung dalam array dokumen tanpa *cost join* tabel yang berat.
> Untuk menjamin konsistensi saat checkout, sistem memanfaatkan **transaksi multi-dokumen MongoDB** dengan level isolasi atomik. Jika server mati atau stok tiba-tiba tidak mencukupi di tengah proses, seluruh perubahan dibatalkan (*rollback otomatis*). Selain itu, sistem dilengkapi logika kompensasi cadangan (*compensating transactions*) untuk menjamin stok tidak hilang meskipun dijalankan pada lingkungan basis data standalone."

### Q2: "Bagaimana sistem mencegah kecurangan pelanggan yang memanipulasi harga barang dari browser?"
> **Jawaban**:
> "Sistem menerapkan prinsip *Zero Client Trust*. Input dari browser pelanggan hanya berupa ID produk dan kuantitas. Nilai harga satuan, subtotal, diskon, dan total tagihan sama sekali tidak pernah diterima atau dipercayai dari klien. Server mengambil data harga resmi langsung dari koleksi `master_product`, memvalidasi kuota dan syarat minimum belanja voucher di koleksi `promotions`, lalu menghitung ulang semua nilai secara independen di sisi server."

### Q3: "Bagaimana cara sistem menangani race condition saat dua pelanggan berebut membeli 1 barang sisa secara bersamaan?"
> **Jawaban**:
> "Sistem menggunakan operator atomik MongoDB `$gte` pada kueri pembaruan:
> `product_repo.dec_stock_if_enough(pid, qty)` yang mengeksekusi:
> `update_one({"_id": pid, "stock": {"$gte": qty}}, {"$inc": {"stock": -qty}})`
> Operator ini dijalankan pada level mesin penyimpanan WiredTiger MongoDB. Pelanggan pertama yang berhasil memotong stok akan mencocokkan dokumen (`matched_count == 1`). Pelanggan kedua yang datang terlambat akan mendapati stok telah menjadi 0 sehingga `matched_count == 0`. Sistem segera menangkap kondisi ini dan membatalkan pesanan pelanggan kedua dengan galat HTTP 409 Conflict yang menginformasikan bahwa stok telah habis."

### Q4: "Bagaimana sistem mengamankan bukti transfer bank yang diunggah pelanggan?"
> **Jawaban**:
> "Bukti transfer diamankan melalui 4 lapisan perlindungan:
> 1. Berkas diuji keabsahannya menggunakan pustaka Pillow (`Image.open().verify()`) untuk memastikan berkas benar-benar berupa citra JPG/PNG dan bukan script berbahaya yang menyamar.
> 2. Nama berkas diganti dengan string acak UUID v4 untuk mencegah serangan *path traversal*.
> 3. Berkas disimpan di subfolder tertutup `uploads/proofs/` yang diblokir dari akses web statis publik langsung.
> 4. Berkas hanya dapat diakses melalui endpoint terautentikasi `GET /orders/<id>/payment-proof`, di mana sistem memverifikasi bahwa pengakses adalah pemilik sah pesanan tersebut atau staf dengan hak akses `admin` (TC-SC-06)."

