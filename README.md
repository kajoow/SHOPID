# ShopID - Backend & Web E-Commerce Platform

Sistem backend aplikasi web e-commerce *SHOPID* berbasis **Python (Flask)** dan **MongoDB**, dirancang khusus untuk memenuhi standar kehandalan tinggi, keamanan data, arsitektur bersih 6-layer, dan kepatuhan penuh terhadap *shopid Complete System Blueprint v1.0*.

---

## 🌟 Fitur Utama Sistem

1. **Arsitektur 6-Layer Bersih & Terisolasi**:
   - `Presentation Layer` (Template Jinja2 & Generative UI)
   - `Routing Layer` (HTTP Blueprints tanpa logika bisnis/query langsung)
   - `Auth & Authorization Layer` (RBAC default-deny, Argon2id, Session Fixation Protection, CSRF)
   - `Service Layer` (Orkestrasi transaksi atomik, kalkulasi diskon, inventori, pelaporan)
   - `Repository Layer` (Satu-satunya layer yang berinteraksi langsung dengan PyMongo)
   - `Database Layer` (MongoDB dengan skema validasi `$jsonSchema` dan indeks performa)
2. **Koleksi Wajib & Tepat 11 Koleksi**:
   - `master_product`, `users`, `categories`, `carts`, `orders`, `stock_movements`, `promotions`, `wishlists`, `reviews`, `notifications`, `audit_logs`.
3. **Autentikasi & RBAC Ketat**:
   - Dua role terpisah: `user` (pelanggan) dan `admin`.
   - Admin dicegah mengakses rute pelanggan (`/cart`, `/checkout`) dengan status HTTP 403 (Keputusan D8).
   - Session Cookie berstandar keamanan tinggi: `HttpOnly`, `SameSite=Lax`, dan `Secure` pada HTTPS.
4. **Checkout Atomik & Idempoten**:
   - Mencegah *double-order* dengan `idempotency_key`.
   - Transaksi multi-dokumen MongoDB atomik: validasi stok, pengurangan stok, pembuatan order snapshot, peningkatan kuota voucher, dan pengosongan keranjang dieksekusi dalam satu sesi transaksi dengan mekanisme kompensasi otomatis jika terjadi kegagalan.
5. **State Machine Transisi Order & Pembayaran**:
   - Pembaruan bersyarat `{_id, order_status: <asal>}` mencegah race condition.
   - Pembatalan pesanan di seluruh status yang diizinkan secara konsisten memulihkan stok, mencatat mutasi `restoration`, mengembalikan kuota voucher, dan menyesuaikan status pembayaran (`paid` $\to$ `refunded`).
   - Unggah bukti transfer aman (verifikasi decoding Pillow, nama UUID acak, penyajian berkas hanya untuk pemilik order dan admin via rute terautentikasi).
6. **Laporan & Dashboard Berbasis Data Nyata (Zero Mock Data)**:
   - Dashboard eksekutif menampilkan KPI penjualan, pesanan selesai, antrean pembayaran, dan produk stok rendah secara real-time.
   - Laporan penjualan harian diagregasi menggunakan MongoDB Aggregation Pipeline dalam zona waktu `Asia/Jakarta` (WIB) hanya dari pesanan berstatus `completed`.
7. **Modul Tambahan Terintegrasi**:
   - Manajemen promosi/voucher dengan kuota dan periode berlaku.
   - Modul Wishlist berbasis set unik.
   - Ulasan produk berperingkat bintang 1-5 dengan validasi kepemilikan transaksi selesai.
   - Notifikasi in-app otomatis untuk pembaruan status dan stok rendah.
   - Log audit sistem (audit trail) untuk menelusuri setiap mutasi data penting.

---

## 🛠️ Persyaratan Sistem

- **Python**: Versi 3.12 atau lebih baru
- **MongoDB**: Versi 7.0 atau lebih baru (Disarankan mode **Replica Set** untuk transaksi multi-dokumen native, didukung pula fallback kompensasi)
- **Virtual Environment**: `venv` bawaan Python
- **Docker** (Opsional, untuk menjalankan replica set MongoDB lokal)

---

## 🚀 Panduan Instalasi & Menjalankan Aplikasi

### 1. Kloning Repositori & Buat Virtual Environment
```bash
git clone <URL_REPOSITORI>
cd kapita_alfa

# Buat virtual environment
python3 -m venv .venv

# Aktifkan virtual environment
# Di Linux/macOS:
source .venv/bin/activate
# Di Windows:
# .venv\Scripts\activate
```

### 2. Instal Dependensi
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

`tzdata` supplies the IANA timezone database on platforms such as Windows that
do not include it with Python.

### 3. Konfigurasi Environment Variables (`.env`)
Salin file `.env.example` menjadi `.env`:
```bash
cp .env.example .env
```
Sesuaikan konfigurasi di dalam file `.env`:
```ini
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=ganti-dengan-kunci-rahasia-panjang-dan-acak-minimal-32-karakter
MONGO_URI=mongodb://127.0.0.1:27017/?replicaSet=rs0&directConnection=true
MONGO_DB_NAME=retailbrain
SESSION_COOKIE_SECURE=false
DEMO_PASSWORD=DemoPassword123!
UPLOAD_DIR=instance/uploads
```

> [!TIP]
> **Menjalankan MongoDB Replica Set Lokal via Docker:**
> ```bash
> docker run -d --name mongo-retailbrain -p 27017:27017 mongo:7 --replSet rs0
> docker exec -it mongo-retailbrain mongosh --eval "rs.initiate({_id: 'rs0', members: [{_id: 0, host: '127.0.0.1:27017'}]})"
> ```

### 4. Inisialisasi Database & Data Demo
Gunakan CLI bawaan Flask yang telah disediakan:

```bash
# 1. Buat 11 koleksi, terapkan $jsonSchema, dan seluruh indeks performa (Bab 11.6)
flask init-db

# 2. Buat akun Admin utama (interaktif, Argon2id hash)
flask create-admin

# 3. Masukkan data kategori, produk awal, voucher, dan user demo untuk simulasi
flask seed-demo
```

### 5. Jalankan Aplikasi
```bash
python run.py
```
Aplikasi akan berjalan di: `http://127.0.0.1:5000`

Login pelanggan tersedia di `/auth/login`, sedangkan login admin memiliki portal terpisah di `/admin/login`.

---

## 🧪 Menjalankan Pengujian Otomatis (Testing)

Seluruh test suite menggunakan database terpisah (`retailbrain_test`) yang diisolasi otomatis.

```bash
# Menjalankan seluruh pengujian unit, integrasi, keamanan, dan E2E
.venv/bin/pytest -v

# Menjalankan pengujian spesifik skenario demo Bab 23.2
.venv/bin/pytest -v tests/e2e/test_demo_scenario.py
```

**Hasil Pengujian Saat Ini**: **89 dari 89 Test Cases Lulus (100% Passed)**.

---

## 🌐 Panduan Deployment Produksi (Bab 19)

Untuk lingkungan produksi, jalankan aplikasi di balik WSGI server **Gunicorn** dan reverse proxy **Nginx** dengan enkripsi SSL/HTTPS:

1. **Jalankan via Gunicorn**:
   ```bash
   gunicorn -w 4 -b 127.0.0.1:5000 --access-logfile - --error-logfile - run:app
   ```
2. **Konfigurasi Reverse Proxy Nginx**:
   ```nginx
   server {
       listen 80;
       server_name store.retailbrain.example;
       return 301 https://$host$request_uri;
   }

   server {
       listen 443 ssl http2;
       server_name store.retailbrain.example;

       ssl_certificate /etc/letsencrypt/live/store.retailbrain.example/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/store.retailbrain.example/privkey.pem;

       client_max_body_size 2M;

       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto https;
       }
   }
   ```
3. **Environment Variabel Produksi Wajib**:
   Set `SESSION_COOKIE_SECURE=true` agar cookie sesi hanya dikirimkan lewat protokol terenkripsi HTTPS.

---

## 📋 Tabel Status Pemenuhan Acceptance Criteria (Bab 24)

| No | Kriteria Penerimaan | Cara Verifikasi | Kelas | Status Aktual |
|:--:|:--------------------|:----------------|:-----:|:-------------:|
| 1 | Registrasi dan autentikasi user berfungsi | TC-AU-01..11 | MVP | **Terpenuhi (Lulus)** |
| 2 | Autentikasi admin berfungsi | Login admin hasil `create-admin` | MVP | **Terpenuhi (Lulus)** |
| 3 | Tepat dua role ditegakkan (User & Admin) | TC-RB-01..07, TC-AU-04 | MVP | **Terpenuhi (Lulus)** |
| 4 | Katalog produk berfungsi (Search, Filter, Sort) | TC-PR-07..12 | MVP | **Terpenuhi (Lulus)** |
| 5 | CRUD produk berfungsi (+ Soft Delete) | TC-PR-01..06 | MVP | **Terpenuhi (Lulus)** |
| 6 | Keranjang belanja berfungsi (Aturan Bab 7.C) | TC-CT-01..09 | MVP | **Terpenuhi (Lulus)** |
| 7 | Checkout pesanan berfungsi | TC-CO-01..08 | MVP | **Terpenuhi (Lulus)** |
| 8 | Pembuatan order atomik & idempoten berfungsi | TC-CO-09..10, TC-CO-07 | MVP | **Terpenuhi (Lulus)** |
| 9 | Inventori diperbarui konsisten (Invarian stok) | TC-CO-11..12, TC-IN-01..05 | MVP | **Terpenuhi (Lulus)** |
| 10 | Admin dapat memproses order (State machine) | TC-OR-01..05 | MVP | **Terpenuhi (Lulus)** |
| 11 | User dapat melacak status pesanan | Linimasa status & riwayat order | MVP | **Terpenuhi (Lulus)** |
| 12 | Status pembayaran berfungsi (Transfer & COD) | TC-OR-06..08, 13 | MVP | **Terpenuhi (Lulus)** |
| 13 | Laporan menampilkan data database nyata | TC-RP-01..02 (Asia/Jakarta) | MVP | **Terpenuhi (Lulus)** |
| 14 | Modul tambahan berfungsi (Voucher, Wishlist, Review, Notif) | TC-VC, TC-WL, TC-RV, TC-RP-03 | Tambahan | **Terpenuhi (Lulus)** |

#   S H O P I D 
 
 
