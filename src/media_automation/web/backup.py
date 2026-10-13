"""Create a new read-only snapshot; never overwrite an existing backup."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
from .original.migration import snapshot_store


def backup_store(database, directory):
    target = Path(directory) / (datetime.now(timezone.utc).strftime('work-%Y%m%dT%H%M%S.%fZ') + '.db')
    return snapshot_store(database, target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    print(f'백업 저장: {backup_store(args.database, args.directory)}')


if __name__ == '__main__':
    main()
