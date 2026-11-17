"""Modul output laporan SmartWarehouse.

Menyediakan tiga keluaran:

* :func:`write_json_report` - ``report.json`` PERSIS sesuai format soal
  (Bagian 5 dokumen TT26-09-SE).
* :func:`print_summary`     - ringkasan tabel di terminal.
* :func:`write_summary_csv` - (nilai tambah) ringkasan per sensor dalam CSV
  ``report_summary.csv`` agar mudah dibuka di Excel/Google Sheets.
"""

import csv
import json
import os
import sys
from typing import Any, Dict, List, Mapping, Optional, TextIO

from .config import JSON_INDENT, OUTPUT_ENCODING
from .processor import SensorResult, count_anomalies_by_type

JSON_ANOMALY_FIELDS: List[str] = ["waktu", "jenis", "nilai"]
"""Field anomali yang ditulis ke report.json (sesuai contoh soal)."""

SUMMARY_CSV_COLUMNS: List[str] = [
    "sensor_id",
    "gudang",
    "status",
    "jumlah_data",
    "jumlah_data_valid",
    "suhu_rata_rata",
    "suhu_min",
    "suhu_max",
    "kelembapan_rata_rata",
    "jumlah_anomali",
    "jenis_anomali",
]

SEPARATOR_WIDTH: int = 92
EMPTY_VALUE: str = "-"


def _ensure_parent_dir(path: str) -> None:
    """Membuat folder induk file output bila belum ada."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)


def _fmt(value: Optional[Any]) -> str:
    """Format nilai untuk ditampilkan; ``None`` menjadi tanda strip."""
    return EMPTY_VALUE if value is None else str(value)


# ---------------------------------------------------------------------------
# report.json
# ---------------------------------------------------------------------------
def build_json_report(results: Mapping[str, SensorResult]) -> Dict[str, Any]:
    """Mengubah hasil processor menjadi struktur ``report.json``.

    Format per sensor::

        "SNS-A01": {
          "jumlah_data_valid": 4,
          "suhu_rata_rata": -17.15,
          "suhu_min": -18.5,
          "suhu_max": -14.2,
          "anomali": [{"waktu": "...", "jenis": "...", "nilai": -14.2}]
        }

    Args:
        results: Hasil :func:`processor.process_readings`.

    Returns:
        Dict siap diserialisasi ke JSON.
    """
    report: Dict[str, Any] = {}
    for sensor_id, result in results.items():
        stat = result["statistik"]
        report[sensor_id] = {
            "jumlah_data_valid": stat["jumlah_data_valid"],
            "suhu_rata_rata": stat["suhu_rata_rata"],
            "suhu_min": stat["suhu_min"],
            "suhu_max": stat["suhu_max"],
            "anomali": [
                {field: anomaly[field] for field in JSON_ANOMALY_FIELDS}
                for anomaly in result["anomali"]
            ],
        }
    return report


def write_json_report(results: Mapping[str, SensorResult], output_path: str) -> str:
    """Menulis ``report.json``.

    Args:
        results: Hasil :func:`processor.process_readings`.
        output_path: Path file JSON tujuan.

    Returns:
        Path absolut file yang ditulis.
    """
    _ensure_parent_dir(output_path)
    with open(output_path, "w", encoding=OUTPUT_ENCODING) as handle:
        json.dump(build_json_report(results), handle, indent=JSON_INDENT, ensure_ascii=False)
        handle.write("\n")
    return os.path.abspath(output_path)


# ---------------------------------------------------------------------------
# report_summary.csv (nilai tambah)
# ---------------------------------------------------------------------------
def build_summary_rows(results: Mapping[str, SensorResult]) -> List[Dict[str, Any]]:
    """Meratakan hasil per sensor menjadi baris-baris ringkasan CSV."""
    rows: List[Dict[str, Any]] = []
    for sensor_id, result in results.items():
        stat = result["statistik"]
        jenis_unik: List[str] = []
        for anomaly in result["anomali"]:
            if anomaly["jenis"] not in jenis_unik:
                jenis_unik.append(anomaly["jenis"])
        rows.append(
            {
                "sensor_id": sensor_id,
                "gudang": result["gudang"],
                "status": result["status"],
                "jumlah_data": stat["jumlah_data"],
                "jumlah_data_valid": stat["jumlah_data_valid"],
                "suhu_rata_rata": stat["suhu_rata_rata"],
                "suhu_min": stat["suhu_min"],
                "suhu_max": stat["suhu_max"],
                "kelembapan_rata_rata": stat["kelembapan_rata_rata"],
                "jumlah_anomali": len(result["anomali"]),
                "jenis_anomali": "|".join(jenis_unik),
            }
        )
    return rows


def write_summary_csv(results: Mapping[str, SensorResult], output_path: str) -> str:
    """(Nilai tambah) Mengekspor ringkasan per sensor ke file CSV.

    Args:
        results: Hasil :func:`processor.process_readings`.
        output_path: Path file CSV tujuan.

    Returns:
        Path absolut file yang ditulis.
    """
    _ensure_parent_dir(output_path)
    with open(output_path, "w", encoding=OUTPUT_ENCODING, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_CSV_COLUMNS)
        writer.writeheader()
        for row in build_summary_rows(results):
            writer.writerow({key: ("" if value is None else value) for key, value in row.items()})
    return os.path.abspath(output_path)


# ---------------------------------------------------------------------------
# Ringkasan terminal
# ---------------------------------------------------------------------------
def print_summary(
    results: Mapping[str, SensorResult],
    source_file: str = "",
    stream: Optional[TextIO] = None,
) -> None:
    """Menampilkan ringkasan laporan di terminal.

    Args:
        results: Hasil :func:`processor.process_readings`.
        source_file: Nama file sumber data (untuk judul).
        stream: Tujuan output (default ``sys.stdout``).
    """
    out = stream or sys.stdout
    line = "=" * SEPARATOR_WIDTH
    thin = "-" * SEPARATOR_WIDTH

    def emit(text: str = "") -> None:
        out.write(text + "\n")

    total_data = sum(r["statistik"]["jumlah_data"] for r in results.values())
    total_anomali = sum(len(r["anomali"]) for r in results.values())
    bermasalah = sum(1 for r in results.values() if r["anomali"])

    emit(line)
    emit("  LAPORAN SMARTWAREHOUSE - PT DINGIN SEGAR LOGISTIK")
    emit(line)
    emit(f"  Sumber data    : {source_file}")
    emit(f"  Total data     : {total_data} baris dari {len(results)} sensor")
    emit(f"  Total anomali  : {total_anomali} ({bermasalah} sensor perlu perhatian)")
    emit(thin)
    emit(
        f"  {'SENSOR':<10}{'GDG':<5}{'DATA':>5}{'VALID':>7}"
        f"{'SUHU AVG':>10}{'SUHU MIN':>10}{'SUHU MAX':>10}{'ANOMALI':>9}  STATUS"
    )
    emit(thin)
    for sensor_id, result in results.items():
        stat = result["statistik"]
        emit(
            f"  {sensor_id:<10}{result['gudang']:<5}"
            f"{stat['jumlah_data']:>5}{stat['jumlah_data_valid']:>7}"
            f"{_fmt(stat['suhu_rata_rata']):>10}{_fmt(stat['suhu_min']):>10}"
            f"{_fmt(stat['suhu_max']):>10}{len(result['anomali']):>9}  {result['status']}"
        )
    emit(thin)

    emit("  Jumlah anomali per jenis:")
    for jenis, jumlah in count_anomalies_by_type(results).items():
        emit(f"    - {jenis:<26}: {jumlah}")
    emit(thin)

    emit("  Detail anomali:")
    if total_anomali == 0:
        emit("    Tidak ada anomali. Seluruh sensor dalam kondisi normal.")
    for sensor_id, result in results.items():
        for anomaly in result["anomali"]:
            emit(f"    [{anomaly['jenis']}] {sensor_id} @ {_fmt(anomaly['waktu'])}")
            emit(f"        {anomaly['keterangan']}")
    emit(line)
