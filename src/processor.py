"""Modul inti pemrosesan data sensor SmartWarehouse.

Tanggung jawab modul ini:

1. Mengelompokkan pembacaan per sensor dan mengurutkannya berdasarkan waktu.
2. Menghitung statistik suhu per sensor (jumlah data valid, rata-rata,
   minimum, maksimum) hanya dari baris yang valid.
3. Mendeteksi 4 aturan anomali:

   * ``SUHU_DI_LUAR_BATAS``       - suhu di luar rentang aman gudang.
   * ``KELEMBAPAN_DI_LUAR_BATAS`` - kelembapan di luar rentang aman gudang.
   * ``DATA_HILANG``              - selisih dua pembacaan berurutan LEBIH DARI
     :data:`config.DATA_HILANG_THRESHOLD_MENIT`.
   * ``DATA_TIDAK_VALID``         - suhu/kelembapan kosong atau bukan angka
     (juga timestamp rusak dan kode gudang tidak dikenal).

Modul ini tidak menulis file apa pun; hasilnya berupa struktur data Python
yang kemudian diformat oleh :mod:`src.reporter`.
"""

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional

from .config import (
    ANOMALI_DATA_HILANG,
    ANOMALI_DATA_TIDAK_VALID,
    ANOMALI_KELEMBAPAN,
    ANOMALI_SUHU,
    BATAS_AMAN,
    DATA_HILANG_THRESHOLD_MENIT,
    DECIMAL_PLACES,
    JENIS_ANOMALI,
    STATUS_NORMAL,
    STATUS_PERLU_PERHATIAN,
    TIMESTAMP_FORMAT,
)
from .parser import Reading

Anomaly = Dict[str, Any]
SensorResult = Dict[str, Any]
Thresholds = Mapping[str, Mapping[str, Any]]

SECONDS_PER_MINUTE: int = 60


# ---------------------------------------------------------------------------
# Utilitas
# ---------------------------------------------------------------------------
def format_timestamp(value: Optional[datetime]) -> Optional[str]:
    """Mengubah datetime menjadi teks sesuai format konfigurasi."""
    return value.strftime(TIMESTAMP_FORMAT) if value is not None else None


def calculate_average(values: List[float]) -> Optional[float]:
    """Menghitung rata-rata secara manual, dibulatkan 2 desimal.

    Args:
        values: Daftar angka.

    Returns:
        Rata-rata yang sudah dibulatkan, atau ``None`` jika daftar kosong.
    """
    if not values:
        return None
    total = 0.0
    for value in values:
        total += value
    return round(total / len(values), DECIMAL_PLACES)


def find_min(values: List[float]) -> Optional[float]:
    """Mencari nilai terkecil secara manual (``None`` jika kosong)."""
    if not values:
        return None
    smallest = values[0]
    for value in values[1:]:
        if value < smallest:
            smallest = value
    return smallest


def find_max(values: List[float]) -> Optional[float]:
    """Mencari nilai terbesar secara manual (``None`` jika kosong)."""
    if not values:
        return None
    largest = values[0]
    for value in values[1:]:
        if value > largest:
            largest = value
    return largest


# ---------------------------------------------------------------------------
# Pengelompokan & pengurutan
# ---------------------------------------------------------------------------
def sort_by_timestamp(readings: List[Reading]) -> List[Reading]:
    """Mengurutkan pembacaan secara kronologis.

    Pembacaan dengan timestamp tidak valid (``None``) diletakkan di akhir,
    lalu diurutkan berdasarkan nomor baris agar hasilnya deterministik.
    """
    return sorted(
        readings,
        key=lambda r: (r.timestamp is None, r.timestamp or datetime.min, r.baris),
    )


def group_by_sensor(readings: List[Reading]) -> Dict[str, List[Reading]]:
    """Mengelompokkan pembacaan per ``sensor_id`` dan mengurutkannya.

    Args:
        readings: Seluruh pembacaan (urutan bebas).

    Returns:
        Dict ``{sensor_id: [Reading, ...]}`` dengan kunci terurut alfabetis
        dan isi setiap grup terurut berdasarkan waktu.
    """
    groups: Dict[str, List[Reading]] = {}
    for reading in readings:
        groups.setdefault(reading.sensor_id, []).append(reading)
    return {sid: sort_by_timestamp(groups[sid]) for sid in sorted(groups)}


# ---------------------------------------------------------------------------
# Statistik
# ---------------------------------------------------------------------------
def compute_statistics(readings: List[Reading]) -> Dict[str, Any]:
    """Menghitung statistik satu sensor dari baris yang VALID saja.

    Sesuai alur alternatif A1, baris yang ditandai ``DATA_TIDAK_VALID``
    tidak dihitung dalam statistik.

    Args:
        readings: Pembacaan satu sensor.

    Returns:
        Dict berisi ``jumlah_data``, ``jumlah_data_valid``,
        ``suhu_rata_rata``, ``suhu_min``, ``suhu_max``, dan
        ``kelembapan_rata_rata``.
    """
    valid = [r for r in readings if r.is_valid]
    suhu_values = [r.suhu for r in valid if r.suhu is not None]
    kelembapan_values = [r.kelembapan for r in valid if r.kelembapan is not None]

    return {
        "jumlah_data": len(readings),
        "jumlah_data_valid": len(valid),
        "suhu_rata_rata": calculate_average(suhu_values),
        "suhu_min": find_min(suhu_values),
        "suhu_max": find_max(suhu_values),
        "kelembapan_rata_rata": calculate_average(kelembapan_values),
    }


# ---------------------------------------------------------------------------
# Aturan anomali
# ---------------------------------------------------------------------------
def make_anomaly(
    waktu: Optional[str], jenis: str, nilai: Any, keterangan: str
) -> Anomaly:
    """Membuat satu catatan anomali.

    ``waktu``, ``jenis``, dan ``nilai`` adalah field yang ditulis ke
    ``report.json``; ``keterangan`` hanya untuk tampilan terminal.
    """
    return {"waktu": waktu, "jenis": jenis, "nilai": nilai, "keterangan": keterangan}


def is_out_of_range(value: float, batas_min: float, batas_max: float) -> bool:
    """``True`` jika ``value`` di luar rentang [min, max] (batas inklusif)."""
    return value < batas_min or value > batas_max


def check_suhu(reading: Reading, batas: Mapping[str, Any]) -> Optional[Anomaly]:
    """Aturan 1 - ``SUHU_DI_LUAR_BATAS``."""
    suhu_min, suhu_max = float(batas["suhu_min"]), float(batas["suhu_max"])
    if reading.suhu is None or not is_out_of_range(reading.suhu, suhu_min, suhu_max):
        return None
    return make_anomaly(
        format_timestamp(reading.timestamp),
        ANOMALI_SUHU,
        reading.suhu,
        f"Suhu {reading.suhu} C di luar batas aman {suhu_min} s/d {suhu_max} C",
    )


def check_kelembapan(reading: Reading, batas: Mapping[str, Any]) -> Optional[Anomaly]:
    """Aturan 2 - ``KELEMBAPAN_DI_LUAR_BATAS``."""
    rh_min, rh_max = float(batas["kelembapan_min"]), float(batas["kelembapan_max"])
    if reading.kelembapan is None or not is_out_of_range(reading.kelembapan, rh_min, rh_max):
        return None
    return make_anomaly(
        format_timestamp(reading.timestamp),
        ANOMALI_KELEMBAPAN,
        reading.kelembapan,
        f"Kelembapan {reading.kelembapan}% di luar batas aman {rh_min}-{rh_max}%",
    )


def check_data_hilang(
    readings: List[Reading], threshold_menit: int = DATA_HILANG_THRESHOLD_MENIT
) -> List[Anomaly]:
    """Aturan 3 - ``DATA_HILANG``.

    Membandingkan setiap pasangan pembacaan berurutan (yang timestamp-nya
    valid). Jika selisihnya LEBIH DARI ``threshold_menit``, anomali dicatat
    pada waktu pembacaan SESUDAH jeda (saat jeda terdeteksi), dengan
    ``nilai`` = lama jeda dalam menit.

    Args:
        readings: Pembacaan satu sensor, sudah terurut waktu.
        threshold_menit: Ambang selisih waktu (menit).

    Returns:
        Daftar anomali ``DATA_HILANG``.
    """
    timed = [r for r in readings if r.timestamp is not None]
    anomalies: List[Anomaly] = []

    for prev, curr in zip(timed, timed[1:]):
        selisih_menit = (curr.timestamp - prev.timestamp).total_seconds() / SECONDS_PER_MINUTE
        if selisih_menit > threshold_menit:
            anomalies.append(
                make_anomaly(
                    format_timestamp(curr.timestamp),
                    ANOMALI_DATA_HILANG,
                    int(selisih_menit) if selisih_menit.is_integer() else selisih_menit,
                    f"Tidak ada data selama {selisih_menit:g} menit sejak "
                    f"{format_timestamp(prev.timestamp)} (ambang {threshold_menit} menit)",
                )
            )
    return anomalies


def check_data_tidak_valid(
    reading: Reading, thresholds: Thresholds = BATAS_AMAN
) -> Optional[Anomaly]:
    """Aturan 4 - ``DATA_TIDAK_VALID``.

    Utamanya suhu/kelembapan kosong atau bukan angka (sesuai soal). Sebagai
    pengaman tambahan, timestamp rusak dan kode gudang yang tidak terdaftar
    juga dicatat di sini. ``nilai`` berisi teks mentah yang tidak valid,
    atau ``None`` jika selnya kosong.
    """
    masalah = list(reading.catatan)
    if reading.gudang and reading.gudang not in thresholds:
        masalah.append(f"kode gudang '{reading.gudang}' tidak terdaftar")
    if not masalah:
        return None
    return make_anomaly(
        format_timestamp(reading.timestamp) or reading.timestamp_raw or None,
        ANOMALI_DATA_TIDAK_VALID,
        reading.nilai_tidak_valid,
        "; ".join(masalah).capitalize(),
    )


def detect_anomalies(
    readings: List[Reading],
    thresholds: Thresholds = BATAS_AMAN,
    threshold_menit: int = DATA_HILANG_THRESHOLD_MENIT,
) -> List[Anomaly]:
    """Menjalankan keempat aturan anomali pada pembacaan satu sensor.

    Args:
        readings: Pembacaan satu sensor, sudah terurut waktu.
        thresholds: Batas aman per gudang.
        threshold_menit: Ambang ``DATA_HILANG`` (menit).

    Returns:
        Daftar anomali, terurut berdasarkan waktu lalu jenis anomali.
    """
    anomalies: List[Anomaly] = []
    for reading in readings:
        invalid = check_data_tidak_valid(reading, thresholds)
        if invalid:
            anomalies.append(invalid)

        batas = thresholds.get(reading.gudang)
        if batas is None:
            continue  # tanpa batas aman, pengecekan rentang tidak bisa dilakukan
        for rule in (check_suhu, check_kelembapan):
            result = rule(reading, batas)
            if result:
                anomalies.append(result)

    anomalies.extend(check_data_hilang(readings, threshold_menit))

    urutan_jenis = {jenis: idx for idx, jenis in enumerate(JENIS_ANOMALI)}
    anomalies.sort(key=lambda a: (a["waktu"] or "", urutan_jenis[a["jenis"]]))
    return anomalies


# ---------------------------------------------------------------------------
# Orkestrasi
# ---------------------------------------------------------------------------
def most_common_gudang(readings: List[Reading]) -> str:
    """Mengambil kode gudang yang paling sering muncul pada satu sensor."""
    counts: Dict[str, int] = {}
    for reading in readings:
        if reading.gudang:
            counts[reading.gudang] = counts.get(reading.gudang, 0) + 1
    return max(counts, key=lambda kode: counts[kode]) if counts else ""


def process_readings(
    readings: List[Reading],
    thresholds: Thresholds = BATAS_AMAN,
    threshold_menit: int = DATA_HILANG_THRESHOLD_MENIT,
) -> Dict[str, SensorResult]:
    """Menjalankan seluruh pipeline: grouping, statistik, dan anomali.

    Args:
        readings: Seluruh pembacaan hasil :func:`parser.read_readings`.
        thresholds: Batas aman per gudang.
        threshold_menit: Ambang ``DATA_HILANG`` (menit).

    Returns:
        Dict ``{sensor_id: hasil}``; setiap hasil berisi ``gudang``,
        ``status``, ``statistik``, dan ``anomali``.
    """
    results: Dict[str, SensorResult] = {}
    for sensor_id, sensor_readings in group_by_sensor(readings).items():
        anomalies = detect_anomalies(sensor_readings, thresholds, threshold_menit)
        results[sensor_id] = {
            "gudang": most_common_gudang(sensor_readings),
            "status": STATUS_PERLU_PERHATIAN if anomalies else STATUS_NORMAL,
            "statistik": compute_statistics(sensor_readings),
            "anomali": anomalies,
        }
    return results


def count_anomalies_by_type(results: Mapping[str, SensorResult]) -> Dict[str, int]:
    """Menghitung jumlah anomali per jenis dari seluruh sensor."""
    counts = {jenis: 0 for jenis in JENIS_ANOMALI}
    for result in results.values():
        for anomaly in result["anomali"]:
            counts[anomaly["jenis"]] += 1
    return counts
