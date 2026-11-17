# SmartWarehouse — PT Dingin Segar Logistik

**Tes Teknis Program Magang TaggIoT 2026 · Junior Software Engineer**
Kode Tes: `TT26-09-SE` · Use Case: `UC-SE-01` — Membuat Laporan Ringkas dari Data Sensor
Peserta: Arya Winata

Modul pengolah data sensor berbasis **Python 3 (Standard Library saja)**. Program ini membaca file CSV hasil ekspor sensor suhu dan kelembapan. Data dikelompokkan per sensor dan diurutkan berdasarkan waktu. Program lalu menghitung statistik suhu, mendeteksi **4 jenis anomali**, dan menghasilkan `report.json` serta ringkasan di terminal.

> Program tidak memakai `pandas`, `numpy`, atau library eksternal lain. Rata-rata, minimum, maksimum, dan selisih waktu dihitung manual agar logikanya terlihat jelas.

---

## 1. Struktur Direktori

```
TT26_SE_AryaWinata/
├── main.py                 # Entry point CLI (argparse, exit code)
├── readings.csv            # Data input dari soal
├── report.json             # Hasil eksekusi (output wajib)
├── report_summary.csv      # Hasil eksekusi (output nilai tambah)
├── README.md
├── src/
│   ├── __init__.py
│   ├── config.py           # Konfigurasi terpusat: batas aman, ambang DATA_HILANG, format waktu
│   ├── parser.py           # Tugas 1 - baca CSV, konversi tipe, tandai baris tidak valid
│   ├── processor.py        # Tugas 2 & 3 - grouping, sorting, statistik, 4 aturan anomali
│   └── reporter.py         # Tugas 4 - report.json, ringkasan terminal, report_summary.csv
└── tests/
    ├── __init__.py
    └── test_processor.py   # Tugas 5 - 17 unit test (unittest)
```

Alur data:

```
readings.csv ─► parser.read_readings() ─► processor.process_readings() ─► reporter
                List[Reading]             {sensor_id: hasil}              ├─ report.json
                                                                          ├─ terminal
                                                                          └─ report_summary.csv
```

Setiap modul punya satu tanggung jawab. `processor` tidak menulis file, dan `reporter` tidak menghitung apa pun. Jadi logika bisnis bisa dipakai ulang di backend dan mudah diuji.

---

## 2. Kebutuhan

- Python **3.8+** (diuji dengan Python 3.13).
- Tidak perlu `pip install` apa pun.

---

## 3. Cara Menjalankan Program

Dari root proyek:

```bash
python main.py readings.csv
```

Perintah ini menampilkan ringkasan di terminal dan menulis `report.json` serta `report_summary.csv`.

Opsi lain:

```bash
python main.py readings.csv -o output/report.json -s output/summary.csv   # lokasi output
python main.py readings.csv --threshold-menit 20                         # ubah batas DATA_HILANG
python main.py readings.csv --no-summary-csv --quiet                     # hanya report.json
python main.py --help
```

| Argumen | Keterangan | Default |
|---|---|---|
| `csv_path` | Path file CSV input (**wajib**) | – |
| `-o`, `--output` | Path file laporan JSON | `report.json` |
| `-s`, `--summary-csv` | Path file ringkasan CSV | `report_summary.csv` |
| `--no-summary-csv` | Tidak membuat ringkasan CSV | – |
| `-t`, `--threshold-menit` | Batas menit untuk `DATA_HILANG` | `15` |
| `-q`, `--quiet` | Tidak menampilkan ringkasan terminal | – |

**Exit code:** `0` = sukses · `1` = file tidak ditemukan · `2` = format CSV tidak valid (atau argumen salah, dari argparse) · `3` = nilai `--threshold-menit` ≤ 0.

### Contoh `report.json` (hasil asli untuk `readings.csv`)

```json
{
  "SNS-A01": {
    "jumlah_data_valid": 4,
    "suhu_rata_rata": -17.15,
    "suhu_min": -18.5,
    "suhu_max": -14.2,
    "anomali": [
      { "waktu": "2026-10-20 08:10", "jenis": "SUHU_DI_LUAR_BATAS", "nilai": -14.2 }
    ]
  },
  "SNS-B01": {
    "jumlah_data_valid": 4, "suhu_rata_rata": 6.0, "suhu_min": 4.2, "suhu_max": 8.6,
    "anomali": [
      { "waktu": "2026-10-20 08:10", "jenis": "SUHU_DI_LUAR_BATAS", "nilai": 8.6 },
      { "waktu": "2026-10-20 08:35", "jenis": "DATA_HILANG", "nilai": 25 }
    ]
  },
  "SNS-B02": {
    "jumlah_data_valid": 2, "suhu_rata_rata": 5.95, "suhu_min": 3.9, "suhu_max": 8.0,
    "anomali": [
      { "waktu": "2026-10-20 08:00", "jenis": "KELEMBAPAN_DI_LUAR_BATAS", "nilai": 85.0 },
      { "waktu": "2026-10-20 08:05", "jenis": "DATA_TIDAK_VALID", "nilai": null }
    ]
  }
}
```

---

## 4. Aturan Bisnis

Semua nilai disimpan di [src/config.py](src/config.py). Batas bersifat **inklusif**.

| Gudang | Produk | Suhu aman | Kelembapan aman |
|---|---|---|---|
| A | Beku | −25 °C s/d −15 °C | 40 % – 80 % |
| B | Segar | 0 °C s/d 8 °C | 40 % – 80 % |

| Kode anomali | Kondisi | `nilai` di report.json |
|---|---|---|
| `SUHU_DI_LUAR_BATAS` | suhu < min atau > max gudangnya | suhu terbaca |
| `KELEMBAPAN_DI_LUAR_BATAS` | kelembapan < 40 atau > 80 | kelembapan terbaca |
| `DATA_HILANG` | selisih dua pembacaan berurutan **> 15 menit** | lama jeda (menit) |
| `DATA_TIDAK_VALID` | suhu/kelembapan kosong atau bukan angka | teks yang tidak valid, atau `null` jika kosong |

Penjelasan hasil `readings.csv`:

| Sensor | Kejadian | Alasan |
|---|---|---|
| SNS-A01 | 08:10 suhu −14.2 °C → anomali | lebih hangat dari −15 °C |
| SNS-B01 | 08:10 suhu 8.6 °C → anomali | di atas 8 °C |
| SNS-B01 | 08:35 `DATA_HILANG` 25 menit | 08:10 → 08:35 = 25 > 15 |
| SNS-B02 | 08:00 kelembapan 85 % → anomali | di atas 80 % |
| SNS-B02 | 08:05 suhu kosong → `DATA_TIDAK_VALID` | baris tidak dihitung statistik (valid = 2) |
| SNS-B02 | 08:10 suhu 8.0 °C → **aman** | batas inklusif |

---

## 5. Cara Menjalankan Unit Test

```bash
python -m unittest discover -v
```

Ada **17 unit test** di [tests/test_processor.py](tests/test_processor.py). Kelima test wajib dari soal ada di kelas `TestWajibSesuaiSoal`:

1. `test_1_perhitungan_rata_rata`: rata-rata dan pembulatan 2 desimal.
2. `test_2_batas_inklusif_suhu_8_di_gudang_b_bukan_anomali`
3. `test_3_data_hilang_jika_selisih_lebih_dari_15_menit`
4. `test_4_data_tidak_valid_dan_tidak_dihitung_statistik`
5. `test_5_file_tidak_ditemukan`: di level fungsi dan CLI (exit code ≠ 0).

Test tambahan mencakup:
- Batas bawah/atas suhu dan kelembapan.
- Selisih tepat 15 menit, yang **bukan** anomali.
- Nilai bukan angka.
- Pengurutan waktu.
- Kecocokan SNS-A01 **persis** dengan contoh output soal.
- Statistik dan anomali semua sensor.
- Tes end-to-end CLI.

---

## 6. Nilai Tambah (Opsional)

1. **Argumen CLI untuk batas menit `DATA_HILANG`**: `--threshold-menit`.
2. **Output tambahan berformat CSV**: `report_summary.csv`, satu baris per sensor. Isinya status, jumlah data, statistik suhu, rata-rata kelembapan, dan jenis anomali.
3. **Type hints** di seluruh fungsi, serta docstring di setiap modul dan fungsi.
4. Ringkasan terminal berbentuk tabel, dan exit code yang jelas untuk otomasi/CI.

---

## 7. Asumsi yang Dipakai

1. **Kolom wajib** adalah `sensor_id, gudang, timestamp, suhu, kelembapan`. Format waktunya `YYYY-MM-DD HH:MM`. Jika header tidak lengkap, program berhenti dengan exit code 2.
2. **Baris tidak valid tidak dihitung dalam statistik sama sekali**, sesuai alur A1. Jadi jika suhu kosong, kelembapan baris itu juga tidak ikut rata-rata. Namun nilai yang masih terbaca **tetap diperiksa** terhadap batas aman, supaya kondisi berbahaya tidak terlewat.
3. Satu baris yang suhu *dan* kelembapannya tidak valid dicatat sebagai **satu** anomali `DATA_TIDAK_VALID`.
4. Selain kasus wajib (nilai kosong/bukan angka), `DATA_TIDAK_VALID` juga dipakai untuk timestamp rusak, `sensor_id`/gudang kosong, dan kode gudang yang tidak terdaftar. Tujuannya agar program tidak crash dan masalahnya tetap terlihat.
5. Baris yang **timestamp-nya valid tetap dihitung untuk deteksi `DATA_HILANG`** walaupun nilai sensornya rusak, karena sensor tetap mengirim data. Baris dengan timestamp rusak diletakkan di akhir dan tidak ikut dihitung jedanya.
6. `DATA_HILANG` dicatat pada **waktu pembacaan setelah jeda**, yaitu saat sensor kembali online dan jeda terdeteksi. `nilai`-nya adalah lama jeda dalam menit. Selisih yang **tepat 15 menit bukan anomali** ("lebih dari 15 menit").
7. `suhu_rata_rata` dibulatkan 2 desimal. `suhu_min` dan `suhu_max` ditulis apa adanya. Jika sensor tidak punya data valid, nilainya `null`.
8. `jumlah_data_valid` adalah jumlah baris tanpa masalah parsing.
9. Urutan sensor di laporan mengikuti abjad `sensor_id`. Anomali tiap sensor diurutkan berdasarkan waktu.
10. Satu sensor diasumsikan berada di satu gudang. Batas aman tetap dicek per baris sesuai kolom `gudang` pada baris tersebut.
