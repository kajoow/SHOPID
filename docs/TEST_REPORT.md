# Laporan Hasil Pengujian Sistem (TEST_REPORT.md)

Laporan ini menyajikan hasil eksekusi pengujian otomatis (*automated testing*) sistem backend **RetailBrain** menggunakan kerangka kerja `pytest`, mencakup pengujian unit, integrasi basis data MongoDB, pengujian keamanan, dan simulasi skenario demonstrasi end-to-end.

---

## 1. Ringkasan Eksekusi Pengujian

- **Waktu Eksekusi**: 16 November 2026
- **Lingkungan Uji**: Linux (Kernel 6.6+), Python 3.12.3, MongoDB 7.0 (Replica Set `rs0`)
- **Basis Data Uji**: `retailbrain_test` (terisolasi dan dibersihkan otomatis per sesi uji)
- **Total Test Cases**: **89 Kasus Uji**
- **Hasil**: **89 Passed (100% Lulus)**
- **Durasi Eksekusi**: **11.16 detik**
- **Status Kegagalan**: 0 Gagal (Zero Failure)

```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.2.0, pluggy-1.7.0
rootdir: /home/paulustimothy/projects/Coba/kapita_alfa
configfile: pytest.ini
collected 89 items

tests/e2e/test_demo_scenario.py .                                        [  1%]
tests/integration/test_additional_features.py ....                       [  5%]
tests/integration/test_auth_rbac.py ................                     [ 23%]
tests/integration/test_cart_checkout.py ...........                      [ 35%]
tests/integration/test_foundation_commands.py ...                        [ 39%]
tests/integration/test_inventory_orders.py ...................           [ 60%]
tests/integration/test_products_catalog.py ..........                    [ 71%]
tests/integration/test_reports_dashboard.py ....                         [ 76%]
tests/security/test_security_headers_csrf.py ..                          [ 78%]
tests/security/test_security_p1_p2.py ..............                     [ 94%]
tests/unit/test_foundation.py .....                                      [100%]

============================= 89 passed in 11.16s ==============================
```

---

## 2. Pemetaan & Status Pengujian Sesuai Bab 17 Blueprint

### A. Registrasi, Login, dan Keamanan Sesi (Bab 17.2)
| ID Test | Skenario Pengujian | Target | Status |
|:-------:|:-------------------|:-------|:------:|
| **TC-AU-01** | Registrasi pengguna baru yang valid | Akun role `user` terbuat, redirect login | **PASSED** |
| **TC-AU-02** | Registrasi dengan email yang sudah ada | Ditolak HTTP 409 Conflict | **PASSED** |
| **TC-AU-03** | Format email dan password tidak valid | Ditolak HTTP 422 dengan pesan per-field | **PASSED** |
| **TC-AU-04** | Upaya injeksi manipulasi `role=admin` | Input diabaikan, role tetap `user` | **PASSED** |
| **TC-AU-05** | Hashing password dengan Argon2id | Dokumen tersimpan dengan format `$argon2id$` | **PASSED** |
| **TC-AU-06** | Autentikasi login dengan kredensial valid | Sesi terbentuk, redirect sesuai role | **PASSED** |
| **TC-AU-07** | Pesan galat generik saat kredensial salah | Pesan identik tanpa membocorkan email | **PASSED** |
| **TC-AU-08** | Upaya login akun nonaktif (`is_active=False`) | Login ditolak | **PASSED** |
| **TC-AU-10** | Logout dan pembersihan sesi | Sesi hangus, akses rute privat redirect | **PASSED** |
| **TC-AU-11** | Pencegahan Session Fixation | Session ID diperbarui saat login sukses | **PASSED** |

### B. Otorisasi Role & Isolasi Akses (Bab 17.3)
| ID Test | Skenario Pengujian | Target | Status |
|:-------:|:-------------------|:-------|:------:|
| **TC-RB-01** | Pengguna biasa (`user`) mengakses rute admin | Ditolak HTTP 403 Forbidden | **PASSED** |
| **TC-RB-02** | Pengguna anonim mengakses rute privat | Redirect HTTP 302 ke halaman login | **PASSED** |
| **TC-RB-03** | Admin mengakses rute belanja pelanggan (`/cart`) | Ditolak HTTP 403 Forbidden (Keputusan D8) | **PASSED** |
| **TC-RB-04** | Pengguna membaca detail order pengguna lain | Ditolak HTTP 404 Not Found (Data Isolation) | **PASSED** |
| **TC-RB-05** | Pengguna membatalkan order pengguna lain | Ditolak HTTP 404 Not Found | **PASSED** |
| **TC-RB-06** | Seluruh rute `/admin/*` untuk user biasa | Seluruh 9 endpoint mengembalikan 403 | **PASSED** |
| **TC-RB-07** | Validasi penegakan tepat dua role | Hanya role `user` dan `admin` yang valid | **PASSED** |

### C. Manajemen Produk & Katalog Publik (Bab 17.4)
| ID Test | Skenario Pengujian | Target | Status |
|:-------:|:-------------------|:-------|:------:|
| **TC-PR-01** | Pembuatan produk baru oleh admin | Produk tersimpan, mutasi `initial` tercatat | **PASSED** |
| **TC-PR-02** | Pendaftaran produk dengan SKU duplikat | Ditolak HTTP 409 Conflict | **PASSED** |
| **TC-PR-03** | Validasi harga minus atau stok bukan integer | Ditolak HTTP 422 Unprocessable Entity | **PASSED** |
| **TC-PR-04** | Pembuatan produk dengan kategori tidak ada | Ditolak HTTP 422 | **PASSED** |
| **TC-PR-05** | Soft delete produk (`is_active=False`) | Dokumen dipertahankan, hilang dari katalog | **PASSED** |
| **TC-PR-06** | Upaya manipulasi stok via PATCH produk | Ditolak (stok hanya lewat mutasi inventori) | **PASSED** |
| **TC-PR-07** | Pencarian parsial berdasarkan nama produk | Hanya menampilkan produk aktif yang cocok | **PASSED** |
| **TC-PR-08** | Pencarian persis berdasarkan SKU produk | Produk yang sesuai berhasil ditampilkan | **PASSED** |
| **TC-PR-09** | Penanganan karakter regex berbahaya (`.*`) | Karakter di-escape, tidak mengeksploitasi DB | **PASSED** |
| **TC-PR-10** | Filter kategori, rentang harga, dan pengurutan | Hasil akurat sesuai filter dan urutan | **PASSED** |
| **TC-PR-11** | Sanitasi upaya injeksi operator NoSQL | Ditolak/dibersihkan tanpa merusak query | **PASSED** |

### D. Keranjang Belanja (Bab 17.5)
| ID Test | Skenario Pengujian | Target | Status |
|:-------:|:-------------------|:-------|:------:|
| **TC-CT-01** | Menambahkan item baru ke keranjang | HTTP 201 Created, item tersimpan di DB | **PASSED** |
| **TC-CT-02** | Menambahkan kembali produk yang sama | Kuantitas digabung secara otomatis | **PASSED** |
| **TC-CT-03** | Validasi kuantitas tidak valid (0, negatif, float) | Ditolak HTTP 400/422 | **PASSED** |
| **TC-CT-04** | Kuantitas melebihi sisa stok fisik | Ditolak HTTP 409 Conflict | **PASSED** |
| **TC-CT-05** | Mengubah kuantitas dan menghapus item | Perubahan tersimpan konsisten | **PASSED** |

### E. Checkout & Pembuatan Order Atomik (Bab 17.6)
| ID Test | Skenario Pengujian | Target | Status |
|:-------:|:-------------------|:-------|:------:|
| **TC-CO-01** | Checkout Pickup + COD | Order terbentuk, stok berkurang, cart kosong | **PASSED** |
| **TC-CO-02** | Checkout Pickup + Transfer Bank | Order berstatus `unpaid`, menunggu bukti | **PASSED** |
| **TC-CO-03** | Checkout dengan keranjang kosong | Ditolak HTTP 400 Bad Request | **PASSED** |
| **TC-CO-04** | Manipulasi total harga oleh klien | Diabaikan, server menghitung ulang harga | **PASSED** |
| **TC-CO-06** | Metode Delivery tanpa alamat pengiriman | Ditolak HTTP 422 | **PASSED** |
| **TC-CO-07** | Submit ganda / refresh (Idempotency Key) | Mengembalikan order yang sama (idempotent) | **PASSED** |

### F. Siklus Transisi Order & Pembayaran (Bab 17.7)
| ID Test | Skenario Pengujian | Target | Status |
|:-------:|:-------------------|:-------|:------:|
| **TC-OR-01** | Alur normal: `pending` $\to$ `completed` | Seluruh transisi sukses, status history utuh | **PASSED** |
| **TC-OR-02** | Transisi status tidak valid (mis. pending ke completed) | Ditolak HTTP 409 Conflict | **PASSED** |
| **TC-OR-03** | Konfirmasi ganda bersamaan (*Race Condition*) | Satu sukses, satu 409 (Optimistic lock) | **PASSED** |
| **TC-OR-04** | Transfer bank belum lunas masuk ke `processing` | Ditolak HTTP 409 (Harus lunas terlebih dahulu) | **PASSED** |
| **TC-OR-05** | Order COD diselesaikan sebelum uang diterima | Ditolak HTTP 409 sampai `mark_cod_paid` | **PASSED** |
| **TC-OR-06** | Unggah bukti transfer berkas JPG valid | Status pembayaran menjadi `awaiting_verification` | **PASSED** |
| **TC-OR-07** | Unggah berkas tidak valid (.txt / file rusak) | Ditolak HTTP 422 Unprocessable Entity | **PASSED** |
| **TC-OR-08** | Verifikasi & penolakan pembayaran oleh admin | Admin verify (`paid`) / reject (`failed`) | **PASSED** |
| **TC-OR-09** | Pelanggan membatalkan order saat `pending` | Order dibatalkan, stok pulih penuh | **PASSED** |
| **TC-OR-10** | Pelanggan membatalkan order setelah `confirmed` | Ditolak HTTP 409 | **PASSED** |
| **TC-OR-11** | Admin membatalkan order saat `processing` | Stok pulih, mutasi `restoration` tercatat | **PASSED** |
| **TC-OR-12** | Pembatalan ganda berurutan | Cancel kedua 409, stok dipulihkan sekali | **PASSED** |
| **TC-OR-13** | Pembatalan pesanan yang telah lunas (`paid`) | Status pembayaran menjadi `refunded` | **PASSED** |
| **TC-OR-14** | Pembatalan pesanan yang menggunakan voucher | Kuota voucher dikembalikan (`used_count` -1) | **PASSED** |
| **TC-OR-15** | Order `completed` menambah metrik penjualan | `sold_count` produk bertambah sesuai qty | **PASSED** |

### G. Inventori & Mutasi Stok (Bab 17.8)
| ID Test | Skenario Pengujian | Target | Status |
|:-------:|:-------------------|:-------|:------:|
| **TC-IN-01** | Penambahan stok fisik (`addition` +50) | Stok bertambah 50, mutasi tercatat | **PASSED** |
| **TC-IN-02** | Koreksi stok opname dengan catatan wajib | Selisih bertanda tersimpan, catatan tercatat | **PASSED** |
| **TC-IN-03** | Koreksi menghasilkan nilai stok negatif | Ditolak HTTP 422 | **PASSED** |
| **TC-IN-04** | Deteksi otomatis produk stok rendah | Muncul pada filter `low_stock=true` | **PASSED** |
| **TC-IN-05** | Invarian stok pada seluruh riwayat mutasi | $after = before + quantity$ dan $after \ge 0$ | **PASSED** |

### H. Pelaporan & Analitik (Bab 17.8)
| ID Test | Skenario Pengujian | Target | Status |
|:-------:|:-------------------|:-------|:------:|
| **TC-RP-01** | Total penjualan hanya dari order `completed` | Order cancelled & pending diabaikan | **PASSED** |
| **TC-RP-02** | Pengelompokan harian zona `Asia/Jakarta` | Format YYYY-MM-DD sesuai zona waktu WIB | **PASSED** |

### I. Keamanan Sistem & Validasi Input (Bab 17.9)
| ID Test | Skenario Pengujian | Target | Status |
|:-------:|:-------------------|:-------|:------:|
| **TC-VA-01** | Input format ObjectId tidak valid di URL | Mengembalikan 404 (Bukan 500 server crash) | **PASSED** |
| **TC-SC-01** | Proteksi CSRF pada permintaan POST | Permintaan tanpa token CSRF ditolak 403 | **PASSED** |
| **TC-SC-02** | Pencegahan Stored XSS pada input teks | Tag script di-escape menjadi teks aman | **PASSED** |
| **TC-SC-03** | Header keamanan HTTP (CSP, nosniff, DENY) | Seluruh security headers terpasang | **PASSED** |
| **TC-SC-04** | Atribut keamanan session cookie | `HttpOnly=True`, `SameSite=Lax` terpasang | **PASSED** |
| **TC-SC-05** | Pencegahan Path Traversal pada berkas unggah | Nama berkas di-hash UUID, folder terisolasi | **PASSED** |
| **TC-SC-06** | Pembatasan akses berkas bukti transfer | Akses oleh user lain ditolak 404/403 | **PASSED** |
| **TC-SC-07** | Penanganan galat tanpa kebocoran traceback | Pesan galat umum tanpa stack trace Python | **PASSED** |
| **TC-SC-08** | Pemindaian rahasia di repositori sumber kode | Tidak ada MONGO_URI atau password plaintext | **PASSED** |
| **TC-SC-09** | Pencegahan kebocoran hash password di respons | Field `password_hash` tidak pernah keluar | **PASSED** |

### J. Skenario Demonstrasi End-to-End (Bab 23.2)
| Langkah | Deskripsi Alur Demonstrasi | Hasil Uji Otomatis |
|:-------:|:---------------------------|:------------------:|
| 1 | Admin login, buat kategori & dua produk dengan stok awal | **PASSED** |
| 2 | Pelanggan mendaftar, login, mencari produk, menambah ke keranjang | **PASSED** |
| 3 | Checkout (pickup + transfer manual), konfirmasi order, stok berkurang | **PASSED** |
| 4 | Pelanggan mengunggah berkas bukti transfer bank | **PASSED** |
| 5 | Admin verifikasi bukti (paid) dan memproses order hingga `completed` | **PASSED** |
| 6 | Pelanggan melihat linimasa status selesai dan riwayat pesanan | **PASSED** |
| 7 | Admin membuka laporan penjualan nyata dan mutasi inventori | **PASSED** |
| 8 | Demonstrasi pembatalan pesanan dan pemulihan stok otomatis | **PASSED** |
| 9 | Demonstrasi penegakan hak akses: user biasa buka `/admin/dashboard` (403) | **PASSED** |

---

## 3. Status Pemenuhan Acceptance Criteria (Bab 24)

| No | Kriteria Penerimaan | Verifikasi | Hasil | Catatan |
|:--:|:--------------------|:----------:|:-----:|:--------|
| 1 | Registrasi dan autentikasi user berfungsi | TC-AU-01..11 | **LULUS** | Argon2id, Session Fixation aman, CSRF 403 |
| 2 | Autentikasi admin berfungsi | Login CLI `create-admin` | **LULUS** | Admin bootstrap aman via env |
| 3 | Tepat dua role ditegakkan | TC-RB-01..07 | **LULUS** | Admin dicegah belanja (D8), user dicegah ke admin |
| 4 | Katalog produk berfungsi | TC-PR-07..12 | **LULUS** | Pencarian aman regex escape, filter & sort berfungsi |
| 5 | CRUD produk berfungsi | TC-PR-01..06 | **LULUS** | Soft delete menjaga riwayat, stok diisolasi ke mutasi |
| 6 | Keranjang belanja berfungsi | TC-CT-01..05 | **LULUS** | Persistensi DB, gabung kuantitas, limit 1-99 |
| 7 | Checkout pesanan berfungsi | TC-CO-01..08 | **LULUS** | Dukungan Pickup/Delivery, COD/Bank Transfer |
| 8 | Pembuatan order berfungsi | TC-CO-09..10, 07 | **LULUS** | Idempotency key, transaksi atomik rollback |
| 9 | Inventori diperbarui konsisten | TC-IN-01..05 | **LULUS** | Invarian $after = before + qty$ terbukti 100% |
| 10 | Admin dapat memproses order | TC-OR-01..05 | **LULUS** | State machine transisi bersyarat anti-race condition |
| 11 | User dapat melacak order | Linimasa detail order | **LULUS** | Status history & linimasa visual |
| 12 | Status pembayaran berfungsi | TC-OR-06..08, 13 | **LULUS** | Verifikasi & penolakan bukti, status refund otomatis |
| 13 | Laporan dari database nyata | TC-RP-01..02 | **LULUS** | Agregasi MongoDB harian zona Asia/Jakarta |
| 14 | Modul tambahan berfungsi | TC-VC, TC-WL, TC-RV | **LULUS** | Voucher, Wishlist, Review bintang & Notifikasi in-app |

