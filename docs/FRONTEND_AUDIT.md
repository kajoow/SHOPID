# RetailBrain - Laporan Audit Frontend (Fase 0)

**Dokumen:** `docs/FRONTEND_AUDIT.md`  
**Tanggal:** 16 November 2026  
**Peran:** Senior Backend Engineer (Python/Flask/MongoDB)  
**Status:** Selesai (Menunggu Konfirmasi User sebelum Masuk Fase 1)  

---

## 1. Ringkasan Eksekutif

Audit ini dilakukan terhadap aset frontend starter (`RetailBrain_Frontend_Starter/rb`) untuk membandingkan kesesuaian antara template Jinja2, berkas statis (CSS/JS), form, aksi AJAX/fetch, dan variabel tampilan dengan spesifikasi resmi pada **Software System Blueprint v1.0** (terutama Bab 5, 7, 11–16).

Prinsip utama yang dipegang:
1. **Tidak mengubah tampilan (desain visual, CSS, palet warna, tipografi, dan layout).**
2. **Utamakan menyesuaikan backend ke frontend** agar kontrak antarmuka pengguna tidak rusak.
3. **Ubah frontend hanya minimal** (seperti menambahkan field tersembunyi `csrf_token` yang terlewat pada form POST, atau penyesuaian endpoint) dan mencatat setiap perubahan secara transparan.
4. **Halaman yang belum disediakan di starter** akan dibuat mengikuti pola desain konsisten dari `base.html`, `admin_base.html`, `_macros.html`, dan `style.css`.

---

## 2. Inventaris Berkas Frontend Starter

| No | Berkas | Deskripsi / Fungsi |
|---|---|---|
| 1 | `app/templates/base.html` | Kerangka layout utama (navbar publik/user, meta CSRF, flash message, footer). |
| 2 | `app/templates/admin_base.html` | Kerangka layout konsol admin (sidebar 11 menu admin, konten dinamis). |
| 3 | `app/templates/_macros.html` | Macro pembantu: format Rupiah `rp(n)`, badge stok `stock_tag(p)`, badge status `status(s)`, kartu produk `pcard(p)`, field form `field(...)`. |
| 4 | `app/templates/public/home.html` | Beranda toko: hero banner, kategori chips, daftar produk terbaru. |
| 5 | `app/templates/public/catalog.html` | Katalog produk: filter kategori, rentang harga, sorting, grid produk, paginasi. |
| 6 | `app/templates/public/product_detail.html` | Detail produk: foto placeholder, SKU, harga, stok, deskripsi, tombol keranjang, wishlist, ulasan. |
| 7 | `app/templates/auth/login.html` | Formulir login akun (email, password, CSRF). |
| 8 | `app/templates/auth/register.html` | Formulir pendaftaran akun pelanggan (nama, email, telepon opsional, password, CSRF). |
| 9 | `app/templates/user/cart.html` | Halaman keranjang belanja: tabel item, ubah qty (+/-), hapus item, ringkasan subtotal/total. |
| 10 | `app/templates/user/checkout.html` | Formulir checkout: kontak, metode pengiriman, alamat, metode pembayaran, voucher, ringkasan belanja. |
| 11 | `app/templates/user/orders.html` | Riwayat pesanan pengguna: tabel daftar nomor order, total belanja, status pemenuhan, status pembayaran. |
| 12 | `app/templates/user/order_detail.html` | Detail & pelacakan pesanan: stepper linimasa, daftar snapshot item, upload bukti transfer, tombol batal order. |
| 13 | `app/templates/admin/dashboard.html` | Dashboard KPI admin: penjualan selesai, order selesai, verifikasi tertunda, stok rendah, order menunggu tindakan. |
| 14 | `app/templates/admin/table.html` | Template generik tabel admin untuk daftar modul dengan kolom & baris dinamis. |
| 15 | `public/static/css/style.css` | Token CSS (warna hijau/navy/merah/kuning, dark mode media query, responsive grid, tabel, kartu, tombol, badge). |
| 16 | `public/static/js/app.js` | Helper asynchronous `api(method, url, body)` dengan header `X-CSRFToken`, toast notification, dan event listener aksi keranjang/wishlist. |

---

## 3. Pemetaan Halaman Frontend -> Rute Blueprint

Berikut adalah pemetaan setiap halaman dan aksi pengguna pada frontend terhadap rute API/Web yang ditentukan di Bab 14 Blueprint:

| Halaman / Komponen | Elemen / Form / Interaksi | HTTP Method & Target URL | Rute Blueprint | Kelas | Kesesuaian |
|---|---|---|---|---|---|
| **Header (base.html)** | Logo beranda | `GET /` | `GET /` (14.2) | MVP | Sesuai |
| | Form pencarian | `GET /products?q=...` | `GET /products` (14.3) | MVP | Sesuai |
| | Menu Katalog | `GET /products` | `GET /products` (14.3) | MVP | Sesuai |
| | Menu Wishlist | `GET /wishlist` | `GET /wishlist` (14.4) | Tambahan | Sesuai (Perlu template user) |
| | Menu Keranjang & Badge | `GET /cart` | `GET /cart` (14.3) | MVP | Sesuai |
| | Menu Pesanan Saya | `GET /orders/my` | `GET /orders/my` (14.3) | MVP | Sesuai |
| | Menu Profil Pengguna | `GET /profile` | `GET /profile` (14.2) | MVP | Sesuai (Perlu template user) |
| | Tombol Keluar (Logout) | `POST /auth/logout` | `POST /auth/logout` (14.2) | MVP | Sesuai (CSRF disertakan) |
| | Tombol Masuk | `GET /auth/login` | `GET /auth/login` (14.2) | MVP | Sesuai |
| | Tombol Daftar | `GET /auth/register` | `GET /auth/register` (14.2) | MVP | Sesuai |
| **Beranda (home.html)** | Chips Kategori | `GET /products?category=<slug>` | `GET /products` (14.3) | MVP | Sesuai |
| | Tombol Tambah ke Keranjang | `fetch POST /cart/items` | `POST /cart/items` (14.3) | MVP | Sesuai (Payload: `{product_id, quantity: 1}`) |
| **Katalog (catalog.html)** | Form Filter & Urutan | `GET /products` (query params) | `GET /products` (14.3) | MVP | Sesuai (`category`, `min_price`, `max_price`, `sort`) |
| | Kartu Produk (pcard) | `GET /products/<id>` | `GET /products/<id>` (14.3) | MVP | Sesuai |
| **Detail Produk (product_detail.html)** | Tombol Tambah ke Keranjang | `fetch POST /cart/items` | `POST /cart/items` (14.3) | MVP | Sesuai |
| | Tombol Simpan Favorit | `fetch POST /wishlist/items` | `POST /wishlist/items` (14.4) | Tambahan | Sesuai (Payload: `{product_id}`) |
| **Autentikasi (login.html)** | Form Login | `POST /auth/login` | `POST /auth/login` (14.2) | MVP | Sesuai (`email`, `password`, `csrf_token`) |
| **Registrasi (register.html)** | Form Registrasi | `POST /auth/register` | `POST /auth/register` (14.2) | MVP | Sesuai (`name`, `email`, `phone`, `password`, `csrf_token`) |
| **Keranjang (cart.html)** | Tombol Kurangi/Tambah Qty | `fetch PATCH /cart/items/<id>` | `PATCH /cart/items/<id>` (14.3) | MVP | Sesuai (Payload: `{quantity}`) |
| | Tombol Hapus Item | `fetch DELETE /cart/items/<id>` | `DELETE /cart/items/<id>` (14.3) | MVP | Sesuai |
| | Link Lanjut Checkout | `GET /checkout` | `GET /checkout` (14.3) | MVP | Sesuai |
| **Checkout (checkout.html)** | Form Buat Pesanan | `POST /orders` | `POST /orders` (14.3) | MVP | Sesuai (Detail field dibahas di bawah) |
| **Pesanan (orders.html)** | Link Detail Order | `GET /orders/<id>` | `GET /orders/<id>` (14.3) | MVP | Sesuai |
| **Detail Order (order_detail.html)** | Form Unggah Bukti Bayar | `POST /orders/<id>/payment-proof` | `POST /orders/<id>/payment-proof` (14.3) | MVP | Butuh perbaikan (tambah `csrf_token`) |
| | Form Batalkan Pesanan | `POST /orders/<id>/cancel` | `POST /orders/<id>/cancel` (14.3) | MVP | Butuh perbaikan (tambah `csrf_token`) |
| **Dashboard Admin (admin/dashboard.html)** | Kartu KPI & Tabel Pending | `GET /admin/dashboard` | `GET /admin/dashboard` (14.5) | MVP | Sesuai |
| | Link Buka Order Admin | `GET /admin/orders/<id>` | `GET /admin/orders/<id>` (14.6) | MVP | Sesuai |
| **Sidebar Admin (admin_base.html)** | Navigasi 11 Menu Admin | `GET /admin/<section>` | Bab 14.5 & 14.6 | MVP & Tambahan | Sesuai dengan seluruh rute admin |

---

## 4. Analisis Ketidakcocokan (Mismatches & Gaps)

Dari pembacaan detail baris demi baris, ditemukan sejumlah ketidakcocokan antara frontend starter dan blueprint:

### A. Keamanan & CSRF Token pada Form HTML
1. **Form Unggah Bukti Pembayaran (`user/order_detail.html` Baris 7):**
   - **Kondisi Frontend:** `<form method="post" action="/orders/{{ order._id }}/payment-proof" enctype="multipart/form-data">` tidak memiliki input hidden `csrf_token`.
   - **Dampak:** Karena backend menerapkan proteksi ketat `Flask-WTF` (`CSRFProtect`), submit form multipart ini akan langsung ditolak dengan status **403 Forbidden**.
   - **Solusi:** Tambahkan `<input type="hidden" name="csrf_token" value="{{ csrf_token() if csrf_token is defined else '' }}">` di dalam form.

2. **Form Pembatalan Pesanan (`user/order_detail.html` Baris 8):**
   - **Kondisi Frontend:** `<form method="post" action="/orders/{{ order._id }}/cancel">` tidak memiliki input hidden `csrf_token`.
   - **Dampak:** Submit form pembatalan pesanan akan ditolak dengan status **403 Forbidden**.
   - **Solusi:** Tambahkan `<input type="hidden" name="csrf_token" value="{{ csrf_token() if csrf_token is defined else '' }}">` di dalam form.

### B. Struktur Data Form Checkout vs Skema Database Bab 12.5
1. **Data Kontak Pelanggan (`contact`):**
   - **Kondisi Frontend:** Form `user/checkout.html` mengirimkan field terpisah: `contact_name` dan `contact_phone`.
   - **Spesifikasi Database (Bab 12.5):** Field tersimpan pada dokumen `orders` adalah objek embedded `contact: {name: "...", phone: "..."}`.
   - **Solusi Penyesuaian Backend:** Backend menerima `contact_name` dan `contact_phone` dari request form, memvalidasinya, dan menyusunnya menjadi objek snapshot `contact` saat pembuatan order. Tampilan form frontend tidak perlu diubah sama sekali.

2. **Alamat Pengiriman (`shipping_address`):**
   - **Kondisi Frontend:** Form `user/checkout.html` menyediakan satu elemen textarea: `<textarea id="shipping_address" name="shipping_address" rows="3"></textarea>`.
   - **Spesifikasi Database (Bab 12.5):** Bila pengiriman adalah `delivery`, `shipping_address` berupa objek embedded `{recipient: "...", line: "...", city: "...", postal_code: "...", notes: "..."}`, dan bernilai `null` bila `pickup`.
   - **Solusi Penyesuaian Backend:** 
     - Bila `fulfillment_method == 'pickup'`, backend menyimpan `shipping_address = None` (null).
     - Bila `fulfillment_method == 'delivery'`, backend memvalidasi agar textarea tidak kosong, lalu memetakan teks alamat ke field `line`, menggunakan `contact_name` sebagai `recipient`, dan field pelengkap default (`city`, `postal_code`, `notes`). Dengan demikian, skema database Bab 12.5 tetap terpenuhi tanpa merusak tampilan checkout.

3. **Nama Field Upload Bukti Transfer:**
   - **Kondisi Frontend:** Input file pada `user/order_detail.html` bertuliskan `<input id="proof" name="proof" type="file" accept="image/png,image/jpeg">`.
   - **Solusi Penyesuaian Backend:** Backend handler `POST /orders/<id>/payment-proof` membaca file melalui `request.files.get('proof')`.

### C. Alur Pratinjau Diskon Voucher (`POST /checkout/voucher`)
- **Kondisi Blueprint:** Bab 14.3 mendefinisikan endpoint `POST /checkout/voucher` yang mengembalikan `{discount, total}`.
- **Kondisi Frontend:** `user/checkout.html` memiliki input `voucher_code` yang dikirim bersama form `POST /orders`, namun tidak memiliki tombol "Terapkan" interaktif dengan fetch di template awal.
- **Solusi:** Backend tetap menyediakan endpoint `POST /checkout/voucher` sesuai Bab 14.3. Pada saat checkout dikirim (`POST /orders`), backend tetap memvalidasi ulang kode voucher di server-side dan menerapkan diskon secara aman. Kami juga dapat menyematkan script ringan untuk live voucher preview jika pengguna menekan tombol enter/terapkan pada input voucher.

### D. Penanganan Idempotency Key
- **Kondisi Frontend:** Form checkout memiliki `<input type="hidden" name="idempotency_key" value="{{ idempotency_key }}">`.
- **Kondisi Backend:** Route `GET /checkout` harus men-generate string UUID v4 baru dan menyertakannya ke context Jinja2. Pada saat `POST /orders`, backend memeriksa indeks unik `idempotency_key` pada koleksi `orders` untuk memastikan sifat idempotent (submit ganda mengembalikan order yang sama tanpa mengurangi stok dua kali).

### E. Halaman-Halaman yang Belum Ada di Starter (Perlu Dibuat)
Starter frontend baru menyertakan sebagian template halaman publik dan keranjang. Beberapa halaman wajib (MVP) dan tambahan yang dirujuk oleh Blueprint belum memiliki file template khusus di starter:
1. **User Module:**
   - `app/templates/user/dashboard.html` (`GET /dashboard`): Ringkasan status belanja pengguna, notifikasi, dan tombol akses cepat.
   - `app/templates/user/profile.html` (`GET /profile`): Informasi profil (nama, telepon, alamat) dan form ganti password (`POST /profile/password`).
   - `app/templates/user/order_confirmation.html` (`GET /orders/<id>/confirmation`): Halaman sukses setelah order terbit, instruksi nomor rekening transfer atau jam pengambilan toko.
   - `app/templates/user/wishlist.html` (`GET /wishlist`): Halaman produk favorit (Tambahan).
   - `app/templates/user/notifications.html` (`GET /notifications`): Daftar notifikasi in-app pengguna (Tambahan).
2. **Admin Module:**
   Starter hanya menyediakan `admin/dashboard.html` dan `admin/table.html` generik. Sesuai Bab 15.2, modul admin membutuhkan antarmuka operasional:
   - `admin/products.html`: Daftar produk lengkap dengan status aktif/nonaktif, modal form tambah produk baru (dengan unggah file gambar), modal form edit produk, dan tombol nonaktifkan produk (soft delete).
   - `admin/categories.html`: Daftar kategori dengan modal form tambah/edit dan tombol nonaktifkan.
   - `admin/inventory.html`: Manajemen stok dengan indikator stok rendah, modal restock (penambahan), dan modal koreksi (stock opname) dengan catatan wajib.
   - `admin/inventory_movements.html`: Riwayat pergerakan stok (append-only audit trail).
   - `admin/orders.html`: Antrean pesanan dengan filter status pemenuhan dan status pembayaran.
   - `admin/order_detail.html`: Detail pesanan admin untuk konfirmasi pesanan, ubah status ke `processing`, `ready_for_pickup`, `completed`, atau `cancelled`.
   - `admin/payments.html`: Antrean verifikasi pembayaran transfer manual, penampil bukti transfer, serta tombol Verifikasi (paid) atau Tolak (failed) disertai catatan alasan.
   - `admin/reports_sales.html`: Laporan rekapitulasi penjualan harian berbasis data nyata agregasi MongoDB.
   - `admin/reports_inventory.html`: Laporan status stok dan ambang batas minimum.
   - *(Tambahan)*: `admin/promotions.html`, `admin/users.html`, `admin/reviews.html`, `admin/audit_logs.html`, `admin/reports_best_sellers.html`.

### F. Kontrak Context Processor Global (`app/__init__.py`)
Agar template `base.html` dan turunannya berjalan mulus, backend harus menyediakan variable context processor global:
1. `current_user`: objek user terautentikasi (atau anonymous proxy) dengan properti:
   - `is_authenticated` (boolean)
   - `role` ('user' atau 'admin')
   - `name` (string nama pengguna)
   - `_id` / `id` (ObjectId)
2. `cart_count`: integer jumlah item di keranjang pengguna saat ini (0 jika belum login atau jika role admin).
3. `csrf_token()`: fungsi generator token CSRF dari `Flask-WTF`.

---

## 5. Rencana Penyesuaian Detail (Action Plan)

### Rencana 1: Penyesuaian Minimal pada File Frontend
1. **Tambahkan token CSRF tersembunyi pada `user/order_detail.html`:**
   - Tambahkan `<input type="hidden" name="csrf_token" value="{{ csrf_token() if csrf_token is defined else '' }}">` pada form upload bukti pembayaran dan form pembatalan pesanan.
2. **Tautan Navigasi Khusus Admin pada `base.html`:**
   - Bila pengguna login sebagai admin (`current_user.role == 'admin'`), tampilkan tautan cepat `Dashboard Admin` (`/admin/dashboard`) pada navbar, dan sembunyikan tautan belanja pelanggan (Keranjang/Wishlist) agar sesuai dengan **Keputusan D8** (admin tidak berbelanja).

### Rencana 2: Penyesuaian Backend ke Frontend
1. **Penerimaan Payload Form & Normalisasi:**
   - Tangkap `contact_name` & `contact_phone` -> simpan ke `contact: {name, phone}`.
   - Tangkap `shipping_address` -> simpan ke `shipping_address: {line, recipient, city, postal_code, notes}` bila delivery, atau `None` bila pickup.
   - Tangkap `request.files['proof']` pada `POST /orders/<id>/payment-proof`.
2. **Format Respons JSON Sesuai Kontrak `app.js` & Bab 14.1:**
   - Sukses: `{"ok": true, "data": {...}}`
   - Gagal: `{"ok": false, "error": {"code": "...", "message": "...", "fields": {...}}}`
   - Memastikan helper `api()` di `app.js` dapat langsung menerima respons sukses maupun pesan error toast tanpa modifikasi JavaScript dasar.
3. **Penyajian File Bukti Pembayaran Terautentikasi:**
   - Sesuai Keputusan Tambahan Blueprint, file bukti pembayaran tidak diletakkan di `/static` publik. Backend menyediakan endpoint terautentikasi `GET /orders/<id>/payment-proof` (hanya dapat diakses pemilik pesanan dan admin) untuk menyajikan gambar bukti transfer secara aman.

### Rencana 3: Pembuatan Template Baru Mengikuti Pola Konsisten
Seluruh template baru yang akan dibangun pada fase-fase berikutnya wajib mematuhi aturan berikut:
- Menggunakan `{% extends "base.html" %}` (untuk pengguna) atau `{% extends "admin_base.html" %}` (untuk admin).
- Memakai macro dari `_macros.html` (`rp`, `stock_tag`, `status`, `pcard`, `field`).
- Memakai token CSS dan class dari `style.css` (`.card`, `.grid`, `.layout`, `.two`, `.btn`, `.btn.ghost`, `.btn.danger`, `.tag`, `.mut`, `.price`, `.scroll`, dll.).
- Menjaga responsivitas tampilan (desktop, tablet, mobile min 360px).

---

## 6. Matriks Verifikasi Kesiapan Masuk Fase 1

| Aspek | Kondisi Saat Ini | Rencana di Fase Terkait |
|---|---|---|
| Struktur folder backend | Belum dibuat di root workspace | Dibuat di **Fase 1** (Bab 18) |
| Konfigurasi env & secret | `.env` belum ada | Dibuat `.env.example` & load env fail-fast di **Fase 1** |
| CLI commands | Belum ada | `flask init-db`, `flask create-admin`, `flask seed-demo` di **Fase 1** |
| Auth & RBAC | Mock di preview.py | Diimplementasikan dengan Argon2id + CSRF + session di **Fase 2** |
| Template frontend starter | Siap di `RetailBrain_Frontend_Starter/rb` | Dipindahkan & diintegrasikan ke `app/templates` dan `public/static` di **Fase 1** |

---

*Laporan audit Fase 0 ini selesai disusun. Sesuai aturan kerja, proses eksekusi dihentikan di sini untuk menunggu konfirmasi dari User sebelum melanjutkan ke Fase 1.*

