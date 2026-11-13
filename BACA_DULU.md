# CPK Tool eFootball

Aplikasi Android untuk **membongkar (disassemble)** dan **menyusun (assemble)** file `.cpk` eFootball mobile.

## Cara mendapatkan file APK (sekali saja, gratis, lewat HP/PC)
1. Buat akun di https://github.com (gratis).
2. Buat repository baru (tombol "New"), beri nama bebas, mis. `cpktool`.
3. Tekan "uploading an existing file", lalu upload SEMUA isi folder ini
   (termasuk folder `.github`). Tekan "Commit changes".
   Tip: kalau folder `.github` tidak ikut terunggah dari HP, upload lewat PC,
   atau buat file `.github/workflows/build.yml` dengan "Add file > Create new file".
4. Buka tab **Actions**. Proses "Build APK" jalan otomatis (+/- 15-25 menit pertama kali).
5. Setelah centang hijau, klik proses itu, di bagian bawah **Artifacts** unduh `CPKTool-APK`
   (zip), ekstrak, lalu pasang file `.apk` di HP (izinkan "install dari sumber tidak dikenal").

## Memakai aplikasi
- Buka aplikasi, beri izin "Akses semua file".
- **Bongkar CPK**: pilih file .cpk -> Mulai. Hasil di folder `<nama>_hasil`.
- Edit file di folder itu (jangan ganti nama file, jangan hapus `_cpk_manifest.json`).
- **Susun CPK**: pilih folder hasil -> (CPK asli terdeteksi otomatis bila masih di
  folder yang sama) -> Mulai. Hasil: `<nama>_BARU.cpk`.
- Simpan cadangan CPK asli sebelum menimpa file di game.

Catatan: Android 11+ memblokir akses ke `Android/data/...`. Salin dulu file CPK ke
folder biasa (mis. Download), kerjakan di sana, lalu salin balik hasilnya.

## Alternatif tanpa APK (Termux / PC)
```
python3 cpk_core.py list     file.cpk
python3 cpk_core.py extract  file.cpk folder_hasil
python3 cpk_core.py build    folder_hasil baru.cpk file.cpk
```
