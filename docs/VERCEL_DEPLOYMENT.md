# Deploy ke Vercel

Proyek ini memakai entrypoint Flask `run.py` dan mendaftarkannya secara eksplisit di
`pyproject.toml` sebagai `run:app`. Hubungkan repository dengan Root Directory di
folder proyek ini; Vercel akan memasang dependensi dari `requirements.txt`.

## Environment variables

Tambahkan variabel berikut pada Vercel Project Settings → Environment Variables,
lalu pilih environment yang digunakan:

- `SECRET_KEY`: nilai acak yang kuat dan rahasia, berbeda dari development.
- `MONGO_URI`: URI koneksi ke MongoDB yang dapat diakses dari Vercel.
- `MONGO_DB_NAME`: nama database produksi (opsional; default `retailbrain`).
- `SESSION_COOKIE_SECURE`: set `true` untuk deployment HTTPS.
- `ALLOW_ADMIN_BOOTSTRAP`: set `false` untuk produksi.

Jangan mengunggah `.env` atau menyimpan kredensial dalam repository.

## Aset dan unggahan

File CSS, JavaScript, dan ilustrasi statis berada di `public/static`. Flask
menggunakan folder itu saat development lokal; pada Vercel endpoint static
Flask dinonaktifkan dan aset disajikan dari direktori `public` oleh Vercel.

Unggahan foto/bukti saat ini disimpan di filesystem melalui `UPLOAD_DIR`.
Filesystem function Vercel tidak menyediakan penyimpanan persisten, jadi fitur
unggah produksi membutuhkan object storage eksternal. Jangan menganggap
`/tmp` sebagai penyimpanan permanen.
