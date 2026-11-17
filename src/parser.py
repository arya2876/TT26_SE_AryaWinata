"""Modul pembacaan dan validasi awal file CSV data sensor.

Modul ini hanya bertugas mengubah baris teks CSV menjadi objek
:class:`Reading` yang bertipe jelas. Nilai yang kosong atau tidak valid
TIDAK dibuang, melainkan disimpan sebagai ``None`` beserta catatannya,
agar modul processor dapat melaporkannya sebagai anomali.
"""

import csv
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .config import (
    CSV_ENCODING,
    REQUIRED_COLUMNS,
    TIMESTAMP_FORMAT,
    UNKNOWN_SENSOR_ID,
)


class CSVFormatError(Exception):
    """Dilempar jika struktur file CSV tidak sesuai spesifikasi."""


@dataclass
class Reading:
    """Satu baris pembacaan sensor yang sudah di-parse.

    Attributes:
        sensor_id: ID sensor, mis. ``SNS-A01``.
        gudang: Kode gudang (huruf kapital), mis. ``A``.
        timestamp: Waktu pembacaan, ``None`` jika tidak dapat di-parse.
        suhu: Suhu dalam derajat Celsius, ``None`` jika kosong/tidak valid.
        kelembapan: Kelembapan relatif (%), ``None`` jika kosong/tidak valid.
        baris: Nomor baris pada file CSV (header = baris 1).
        timestamp_raw: Teks timestamp asli dari file.
        suhu_raw: Teks suhu asli dari file.
        kelembapan_raw: Teks kelembapan asli dari file.
        catatan: Daftar masalah yang ditemukan saat parsing baris ini.
    """

    sensor_id: str
    gudang: str
    timestamp: Optional[datetime]
    suhu: Optional[float]
    kelembapan: Optional[float]
    baris: int = 0
    timestamp_raw: str = ""
    suhu_raw: str = ""
    kelembapan_raw: str = ""
    catatan: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """``True`` jika tidak ada masalah parsing pada baris ini."""
        return not self.catatan

    @property
    def nilai_tidak_valid(self) -> Optional[str]:
        """Teks mentah suhu/kelembapan yang gagal di-parse.

        Mengembalikan ``None`` jika selnya kosong (atau tidak ada nilai
        numerik yang rusak), sehingga di JSON tampil sebagai ``null``.
        """
        if self.suhu is None and self.suhu_raw:
            return self.suhu_raw
        if self.kelembapan is None and self.kelembapan_raw:
            return self.kelembapan_raw
        return None


def parse_number(raw: Optional[str], nama_kolom: str) -> Tuple[Optional[float], Optional[str]]:
    """Mengubah teks menjadi float beserta pesan error bila gagal.

    Args:
        raw: Teks mentah dari sel CSV (boleh ``None``).
        nama_kolom: Nama kolom, dipakai untuk menyusun pesan error.

    Returns:
        Tuple ``(nilai, pesan_error)``. Jika berhasil, ``pesan_error``
        bernilai ``None``; jika gagal, ``nilai`` bernilai ``None``.
    """
    text = (raw or "").strip()
    if not text:
        return None, f"nilai {nama_kolom} kosong"
    try:
        value = float(text)
    except ValueError:
        return None, f"nilai {nama_kolom} bukan angka ('{text}')"
    if value != value or value in (float("inf"), float("-inf")):
        return None, f"nilai {nama_kolom} bukan angka hingga ('{text}')"
    return value, None


def parse_timestamp(raw: Optional[str]) -> Tuple[Optional[datetime], Optional[str]]:
    """Mengubah teks timestamp menjadi :class:`datetime`.

    Args:
        raw: Teks timestamp sesuai :data:`config.TIMESTAMP_FORMAT`.

    Returns:
        Tuple ``(datetime, pesan_error)`` dengan pola yang sama seperti
        :func:`parse_number`.
    """
    text = (raw or "").strip()
    if not text:
        return None, "timestamp kosong"
    try:
        return datetime.strptime(text, TIMESTAMP_FORMAT), None
    except ValueError:
        return None, f"format timestamp tidak valid ('{text}')"


def parse_row(row: Dict[str, Optional[str]], nomor_baris: int) -> Reading:
    """Mengubah satu baris dict CSV menjadi objek :class:`Reading`.

    Args:
        row: Satu baris hasil :class:`csv.DictReader`.
        nomor_baris: Nomor baris di file (untuk pelacakan error).

    Returns:
        Objek :class:`Reading`; masalah parsing dicatat di ``catatan``.
    """
    catatan: List[str] = []

    sensor_id = (row.get("sensor_id") or "").strip()
    if not sensor_id:
        sensor_id = UNKNOWN_SENSOR_ID
        catatan.append("sensor_id kosong")

    gudang = (row.get("gudang") or "").strip().upper()
    if not gudang:
        catatan.append("kode gudang kosong")

    timestamp_raw = (row.get("timestamp") or "").strip()
    timestamp, err_ts = parse_timestamp(timestamp_raw)
    suhu, err_suhu = parse_number(row.get("suhu"), "suhu")
    kelembapan, err_rh = parse_number(row.get("kelembapan"), "kelembapan")

    catatan.extend(err for err in (err_ts, err_suhu, err_rh) if err)

    return Reading(
        sensor_id=sensor_id,
        gudang=gudang,
        timestamp=timestamp,
        suhu=suhu,
        kelembapan=kelembapan,
        baris=nomor_baris,
        timestamp_raw=timestamp_raw,
        suhu_raw=(row.get("suhu") or "").strip(),
        kelembapan_raw=(row.get("kelembapan") or "").strip(),
        catatan=catatan,
    )


def read_readings(file_path: str) -> List[Reading]:
    """Membaca seluruh pembacaan sensor dari file CSV.

    Args:
        file_path: Path ke file CSV input.

    Returns:
        Daftar :class:`Reading` sesuai urutan baris di file.

    Raises:
        FileNotFoundError: Jika file tidak ditemukan / bukan file.
        CSVFormatError: Jika file kosong atau kolom wajib tidak lengkap.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File input tidak ditemukan: '{file_path}'")

    readings: List[Reading] = []
    with open(file_path, "r", encoding=CSV_ENCODING, newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise CSVFormatError(f"File CSV kosong atau tidak memiliki header: '{file_path}'")

        header = [name.strip().lower() for name in reader.fieldnames]
        missing = [col for col in REQUIRED_COLUMNS if col not in header]
        if missing:
            raise CSVFormatError(
                "Kolom wajib tidak ditemukan pada header CSV: " + ", ".join(missing)
            )
        reader.fieldnames = header

        # Header berada di baris 1, sehingga data dimulai dari baris 2.
        for nomor_baris, row in enumerate(reader, start=2):
            cells = [value for key, value in row.items() if key is not None]
            if all(not (value or "").strip() for value in cells):
                continue  # lewati baris yang seluruh selnya kosong
            readings.append(parse_row(row, nomor_baris))

    return readings
