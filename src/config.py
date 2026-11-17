"""Konfigurasi terpusat aplikasi SmartWarehouse.

Seluruh batas aman, format waktu, dan parameter deteksi anomali disimpan
di sini agar modul logika bebas dari *magic numbers*. Nilai diambil dari
dokumen soal TT26-09-SE (Bagian 3 dan 5). Ubah nilai di file ini untuk
menyesuaikan perilaku program tanpa menyentuh kode logika.
"""

from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Format data input/output
# ---------------------------------------------------------------------------
TIMESTAMP_FORMAT: str = "%Y-%m-%d %H:%M"
"""Format timestamp pada file CSV input dan pada laporan output."""

CSV_ENCODING: str = "utf-8-sig"
"""Encoding file CSV input (``-sig`` agar BOM dari Excel ikut ditangani)."""

OUTPUT_ENCODING: str = "utf-8"
"""Encoding file output (JSON dan CSV ringkasan)."""

REQUIRED_COLUMNS: Tuple[str, ...] = (
    "sensor_id",
    "gudang",
    "timestamp",
    "suhu",
    "kelembapan",
)
"""Kolom wajib yang harus ada pada header file CSV."""

UNKNOWN_SENSOR_ID: str = "TIDAK_DIKENAL"
"""ID pengganti untuk baris yang kolom ``sensor_id``-nya kosong."""

# ---------------------------------------------------------------------------
# Batas aman per gudang (INKLUSIF: nilai tepat di batas dianggap AMAN)
# ---------------------------------------------------------------------------
BATAS_AMAN: Dict[str, Dict[str, object]] = {
    "A": {
        "nama": "Gudang A - Produk Beku",
        "suhu_min": -25.0,
        "suhu_max": -15.0,
        "kelembapan_min": 40.0,
        "kelembapan_max": 80.0,
    },
    "B": {
        "nama": "Gudang B - Produk Segar",
        "suhu_min": 0.0,
        "suhu_max": 8.0,
        "kelembapan_min": 40.0,
        "kelembapan_max": 80.0,
    },
}
"""Batas aman suhu (derajat Celsius) dan kelembapan (%) per kode gudang."""

# ---------------------------------------------------------------------------
# Parameter deteksi DATA_HILANG
# ---------------------------------------------------------------------------
INTERVAL_NORMAL_MENIT: int = 5
"""Interval pengiriman data normal setiap sensor (menit)."""

DATA_HILANG_THRESHOLD_MENIT: int = 15
"""Selisih waktu dua pembacaan berurutan yang LEBIH DARI nilai ini
dianggap anomali ``DATA_HILANG`` (sensor dianggap offline)."""

# ---------------------------------------------------------------------------
# Kode jenis anomali (4 aturan)
# ---------------------------------------------------------------------------
ANOMALI_SUHU: str = "SUHU_DI_LUAR_BATAS"
ANOMALI_KELEMBAPAN: str = "KELEMBAPAN_DI_LUAR_BATAS"
ANOMALI_DATA_HILANG: str = "DATA_HILANG"
ANOMALI_DATA_TIDAK_VALID: str = "DATA_TIDAK_VALID"

JENIS_ANOMALI: List[str] = [
    ANOMALI_SUHU,
    ANOMALI_KELEMBAPAN,
    ANOMALI_DATA_HILANG,
    ANOMALI_DATA_TIDAK_VALID,
]
"""Urutan baku jenis anomali (dipakai untuk ringkasan & pengurutan)."""

# ---------------------------------------------------------------------------
# Status sensor (untuk ringkasan terminal & CSV)
# ---------------------------------------------------------------------------
STATUS_NORMAL: str = "NORMAL"
STATUS_PERLU_PERHATIAN: str = "PERLU_PERHATIAN"

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
DEFAULT_REPORT_JSON: str = "report.json"
DEFAULT_SUMMARY_CSV: str = "report_summary.csv"
DECIMAL_PLACES: int = 2
"""Jumlah angka desimal pembulatan rata-rata."""
JSON_INDENT: int = 2
