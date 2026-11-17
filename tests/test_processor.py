"""Unit test SmartWarehouse.

Lima test WAJIB dari soal (Tugas 5) ada di kelas ``TestWajibSesuaiSoal``:
perhitungan rata-rata, batas inklusif, data hilang, data tidak valid, dan
file tidak ditemukan. Kelas lain adalah test tambahan.

Jalankan dari root proyek::

    python -m unittest discover -v
"""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from typing import List, Optional

from main import EXIT_FILE_NOT_FOUND, EXIT_OK, main
from src.config import (
    ANOMALI_DATA_HILANG,
    ANOMALI_DATA_TIDAK_VALID,
    ANOMALI_KELEMBAPAN,
    ANOMALI_SUHU,
    STATUS_NORMAL,
)
from src.parser import Reading, parse_row, read_readings
from src.processor import (
    calculate_average,
    check_data_hilang,
    compute_statistics,
    detect_anomalies,
    group_by_sensor,
    process_readings,
)
from src.reporter import build_json_report

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_CSV = os.path.join(PROJECT_ROOT, "readings.csv")


def make_reading(
    sensor_id: str = "SNS-T01",
    gudang: str = "B",
    waktu: str = "2026-10-20 08:00",
    suhu: Optional[str] = "5.0",
    kelembapan: Optional[str] = "70",
    baris: int = 2,
) -> Reading:
    """Membuat Reading lewat parser agar perilakunya sama dengan data asli."""
    row = {
        "sensor_id": sensor_id,
        "gudang": gudang,
        "timestamp": waktu,
        "suhu": suhu,
        "kelembapan": kelembapan,
    }
    return parse_row(row, baris)


def jenis_anomali(readings: List[Reading]) -> List[str]:
    """Mengambil daftar jenis anomali dari hasil deteksi."""
    return [a["jenis"] for a in detect_anomalies(readings)]


class TestWajibSesuaiSoal(unittest.TestCase):
    """Lima unit test yang diwajibkan soal (Tugas 5)."""

    def test_1_perhitungan_rata_rata(self) -> None:
        """Rata-rata suhu SNS-A01 = (-18.5 - 18.1 - 14.2 - 17.8) / 4 = -17.15."""
        self.assertEqual(calculate_average([-18.5, -18.1, -14.2, -17.8]), -17.15)
        # Pembulatan 2 desimal: (3.9 + 8.0 + 5.0) / 3 = 5.6333... -> 5.63
        self.assertEqual(calculate_average([3.9, 8.0, 5.0]), 5.63)

    def test_2_batas_inklusif_suhu_8_di_gudang_b_bukan_anomali(self) -> None:
        reading = make_reading(gudang="B", suhu="8.0", kelembapan="79")
        self.assertEqual(jenis_anomali([reading]), [])

    def test_3_data_hilang_jika_selisih_lebih_dari_15_menit(self) -> None:
        readings = [
            make_reading(waktu="2026-10-20 08:10"),
            make_reading(waktu="2026-10-20 08:35"),
        ]
        anomalies = check_data_hilang(readings, threshold_menit=15)
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["jenis"], ANOMALI_DATA_HILANG)
        self.assertEqual(anomalies[0]["waktu"], "2026-10-20 08:35")
        self.assertEqual(anomalies[0]["nilai"], 25)

    def test_4_data_tidak_valid_dan_tidak_dihitung_statistik(self) -> None:
        readings = [
            make_reading(waktu="2026-10-20 08:00", suhu="3.9", kelembapan="85"),
            make_reading(waktu="2026-10-20 08:05", suhu="", kelembapan="78"),
            make_reading(waktu="2026-10-20 08:10", suhu="8.0", kelembapan="79"),
        ]
        self.assertIn(ANOMALI_DATA_TIDAK_VALID, jenis_anomali(readings))
        stat = compute_statistics(readings)
        self.assertEqual(stat["jumlah_data_valid"], 2)
        self.assertEqual(stat["suhu_rata_rata"], 5.95)

    def test_5_file_tidak_ditemukan(self) -> None:
        missing = os.path.join(PROJECT_ROOT, "tidak_ada.csv")
        with self.assertRaises(FileNotFoundError):
            read_readings(missing)
        # Di level CLI: pesan error jelas & exit code bukan 0 (alur A2).
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = main([missing])
        self.assertEqual(exit_code, EXIT_FILE_NOT_FOUND)
        self.assertNotEqual(exit_code, 0)
        self.assertIn("tidak ditemukan", stderr.getvalue())


class TestAturanAnomaliTambahan(unittest.TestCase):
    """Test tambahan untuk kasus batas tiap aturan."""

    def test_suhu_di_atas_batas_gudang_a(self) -> None:
        anomalies = detect_anomalies([make_reading(gudang="A", suhu="-14.2", kelembapan="55")])
        self.assertEqual(anomalies, [{
            "waktu": "2026-10-20 08:00",
            "jenis": ANOMALI_SUHU,
            "nilai": -14.2,
            "keterangan": anomalies[0]["keterangan"],
        }])

    def test_suhu_tepat_batas_bawah_aman_dan_di_bawahnya_anomali(self) -> None:
        self.assertEqual(jenis_anomali([make_reading(gudang="B", suhu="0")]), [])
        self.assertEqual(jenis_anomali([make_reading(gudang="B", suhu="-0.1")]), [ANOMALI_SUHU])
        self.assertEqual(jenis_anomali([make_reading(gudang="A", suhu="-25", kelembapan="50")]), [])

    def test_kelembapan_batas_inklusif(self) -> None:
        self.assertEqual(jenis_anomali([make_reading(kelembapan="80")]), [])
        self.assertEqual(jenis_anomali([make_reading(kelembapan="40")]), [])
        self.assertEqual(jenis_anomali([make_reading(kelembapan="85")]), [ANOMALI_KELEMBAPAN])
        self.assertEqual(jenis_anomali([make_reading(kelembapan="39")]), [ANOMALI_KELEMBAPAN])

    def test_selisih_tepat_15_menit_bukan_data_hilang(self) -> None:
        readings = [
            make_reading(waktu="2026-10-20 08:00"),
            make_reading(waktu="2026-10-20 08:15"),
        ]
        self.assertEqual(check_data_hilang(readings, threshold_menit=15), [])

    def test_nilai_bukan_angka_menjadi_data_tidak_valid(self) -> None:
        anomalies = detect_anomalies([make_reading(suhu="abc")])
        self.assertEqual([a["jenis"] for a in anomalies], [ANOMALI_DATA_TIDAK_VALID])
        self.assertEqual(anomalies[0]["nilai"], "abc")

    def test_suhu_kosong_nilai_null(self) -> None:
        anomalies = detect_anomalies([make_reading(suhu="")])
        self.assertIsNone(anomalies[0]["nilai"])

    def test_grouping_dan_urut_waktu(self) -> None:
        readings = [
            make_reading("SNS-B01", waktu="2026-10-20 08:10"),
            make_reading("SNS-A01", gudang="A", suhu="-18", kelembapan="50"),
            make_reading("SNS-B01", waktu="2026-10-20 08:00"),
        ]
        grouped = group_by_sensor(readings)
        self.assertEqual(list(grouped), ["SNS-A01", "SNS-B01"])
        self.assertLess(grouped["SNS-B01"][0].timestamp, grouped["SNS-B01"][1].timestamp)


class TestIntegrasiReadingsCsv(unittest.TestCase):
    """Integrasi parser -> processor -> reporter terhadap readings.csv soal."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = build_json_report(process_readings(read_readings(SAMPLE_CSV)))

    def test_sns_a01_sama_persis_dengan_contoh_output_soal(self) -> None:
        expected = {
            "jumlah_data_valid": 4,
            "suhu_rata_rata": -17.15,
            "suhu_min": -18.5,
            "suhu_max": -14.2,
            "anomali": [
                {"waktu": "2026-10-20 08:10", "jenis": "SUHU_DI_LUAR_BATAS", "nilai": -14.2}
            ],
        }
        self.assertEqual(self.report["SNS-A01"], expected)

    def test_statistik_semua_sensor(self) -> None:
        def stat(sid: str) -> tuple:
            s = self.report[sid]
            return (s["jumlah_data_valid"], s["suhu_rata_rata"], s["suhu_min"], s["suhu_max"])

        self.assertEqual(stat("SNS-B01"), (4, 6.0, 4.2, 8.6))
        self.assertEqual(stat("SNS-B02"), (2, 5.95, 3.9, 8.0))

    def test_anomali_semua_sensor(self) -> None:
        def ringkas(sid: str) -> list:
            return [(a["waktu"], a["jenis"], a["nilai"]) for a in self.report[sid]["anomali"]]

        self.assertEqual(ringkas("SNS-B01"), [
            ("2026-10-20 08:10", ANOMALI_SUHU, 8.6),
            ("2026-10-20 08:35", ANOMALI_DATA_HILANG, 25),
        ])
        self.assertEqual(ringkas("SNS-B02"), [
            ("2026-10-20 08:00", ANOMALI_KELEMBAPAN, 85.0),
            ("2026-10-20 08:05", ANOMALI_DATA_TIDAK_VALID, None),
        ])

    def test_sensor_tanpa_anomali_berstatus_normal(self) -> None:
        results = process_readings([make_reading(), make_reading(waktu="2026-10-20 08:05")])
        self.assertEqual(results["SNS-T01"]["status"], STATUS_NORMAL)

    def test_cli_end_to_end_menulis_report_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_json = os.path.join(tmp, "report.json")
            out_csv = os.path.join(tmp, "summary.csv")
            with redirect_stdout(io.StringIO()):
                exit_code = main([SAMPLE_CSV, "-o", out_json, "-s", out_csv])
            self.assertEqual(exit_code, EXIT_OK)
            with open(out_json, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), self.report)
            self.assertTrue(os.path.isfile(out_csv))


if __name__ == "__main__":
    unittest.main()
