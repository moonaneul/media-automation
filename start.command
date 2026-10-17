#!/bin/zsh
set -eu
cd -- "$(dirname -- "$0")"
if [[ ! -x .venv/bin/python ]]; then
  print '이 폴더의 Python 실행 환경(.venv)이 없습니다. 기존 환경을 확인해 주세요.'
  exit 1
fi
export PYTHONDONTWRITEBYTECODE=1
exec .venv/bin/python scripts/start_primary.py "$@"
