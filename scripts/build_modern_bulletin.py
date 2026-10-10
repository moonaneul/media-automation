"""Build a separate modern design preview from the same numbered bulletin data."""
import argparse
from pathlib import Path
import yaml
from media_automation.weekly_data.models import SundayData
from media_automation.bulletin.document import build_bulletin_document
from media_automation.bulletin.modern import render_modern_bulletin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--weekly', required=True, help='호수가 포함된 주보용 YAML')
    parser.add_argument('--output', required=True)
    parser.add_argument('--photo', default=str(Path(__file__).resolve().parents[1] / 'assets/bulletin/autumn_soft_v2.png'))
    args = parser.parse_args()
    weekly = SundayData.model_validate(yaml.safe_load(Path(args.weekly).read_text(encoding='utf-8-sig')))
    if not Path(args.photo).is_file():
        raise FileNotFoundError(args.photo)
    document = build_bulletin_document(weekly)
    print(render_modern_bulletin(document, args.output, Path(args.photo)))


if __name__ == '__main__':
    main()
