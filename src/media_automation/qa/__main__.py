"""Command-line entry point: python -m media_automation.qa ..."""
import argparse
from pathlib import Path

from .inspection import inspect_file, save_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only PPTX/PDF structure checks")
    parser.add_argument("source", type=Path)
    parser.add_argument("--service", choices=("wednesday", "sunday", "friday_zoom", "friday_in_person", "bulletin"), default="wednesday")
    parser.add_argument("--reference", help="Expected scripture verse range, e.g. '삼상 17:41~49'")
    parser.add_argument("--report", required=True, type=Path, help="Separate JSON report destination")
    args = parser.parse_args()
    if args.source.resolve() == args.report.resolve():
        parser.error("The report path cannot be the source path")
    report = inspect_file(args.source, service=args.service, expected_reference=args.reference)
    destination = save_report(report, args.report)
    print(f"검수 보고서: {destination}")
    print(f"오류 {report['summary']['error']} / 확인 필요 {report['summary']['review']}")
    return 1 if report["summary"]["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
