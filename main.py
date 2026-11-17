"""Entry point CLI SmartWarehouse - PT Dingin Segar Logistik.

Contoh pemakaian::

    python main.py readings.csv
    python main.py readings.csv -o output/report.json -s output/summary.csv
    python main.py readings.csv --threshold-menit 20 --no-summary-csv
"""

import argparse
import sys
from typing import List, Optional

from src.config import (
    DATA_HILANG_THRESHOLD_MENIT,
    DEFAULT_REPORT_JSON,
    DEFAULT_SUMMARY_CSV,
)
from src.parser import CSVFormatError, read_readings
from src.processor import process_readings
from src.reporter import print_summary, write_json_report, write_summary_csv

EXIT_OK: int = 0
EXIT_FILE_NOT_FOUND: int = 1
EXIT_INVALID_FORMAT: int = 2
EXIT_INVALID_ARGUMENT: int = 3


def build_arg_parser() -> argparse.ArgumentParser:
    """Membangun parser argumen baris perintah."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description=(
            "Memproses data sensor gudang (CSV), menghitung statistik, "
            "mendeteksi anomali, dan menghasilkan report.json."
        ),
    )
    parser.add_argument("csv_path", help="Path file CSV input, mis. readings.csv")
    parser.add_argument(
        "-o", "--output",
        default=DEFAULT_REPORT_JSON,
        help=f"Path file laporan JSON (default: {DEFAULT_REPORT_JSON})",
    )
    parser.add_argument(
        "-s", "--summary-csv",
        default=DEFAULT_SUMMARY_CSV,
        help=f"Path file ringkasan CSV (default: {DEFAULT_SUMMARY_CSV})",
    )
    parser.add_argument(
        "--no-summary-csv",
        action="store_true",
        help="Jangan membuat file ringkasan CSV",
    )
    parser.add_argument(
        "-t", "--threshold-menit",
        type=int,
        default=DATA_HILANG_THRESHOLD_MENIT,
        help=(
            "Batas menit untuk anomali DATA_HILANG "
            f"(default: {DATA_HILANG_THRESHOLD_MENIT})"
        ),
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Jangan tampilkan ringkasan di terminal",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Menjalankan pipeline: baca CSV -> proses -> tulis laporan.

    Args:
        argv: Daftar argumen (default: ``sys.argv[1:]``).

    Returns:
        Kode keluar proses (0 = sukses, selain 0 = gagal).
    """
    args = build_arg_parser().parse_args(argv)

    if args.threshold_menit <= 0:
        print("[ERROR] --threshold-menit harus bilangan bulat positif.", file=sys.stderr)
        return EXIT_INVALID_ARGUMENT

    try:
        readings = read_readings(args.csv_path)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        print("        Pastikan path file benar, contoh: python main.py readings.csv",
              file=sys.stderr)
        return EXIT_FILE_NOT_FOUND
    except (CSVFormatError, UnicodeDecodeError) as exc:
        print(f"[ERROR] Format file tidak valid: {exc}", file=sys.stderr)
        return EXIT_INVALID_FORMAT

    results = process_readings(readings, threshold_menit=args.threshold_menit)

    if not args.quiet:
        print_summary(results, source_file=args.csv_path)

    json_path = write_json_report(results, args.output)
    print(f"[OK] Laporan JSON ditulis ke  : {json_path}")

    if not args.no_summary_csv:
        csv_path = write_summary_csv(results, args.summary_csv)
        print(f"[OK] Ringkasan CSV ditulis ke : {csv_path}")

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
