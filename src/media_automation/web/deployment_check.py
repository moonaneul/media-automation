"""Read-only production prerequisites. Never prints secrets or weekly content."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
from urllib.parse import urlsplit


def check_deployment(root, database, *, environ=None):
    env = os.environ if environ is None else environ
    root, database = Path(root), Path(database)
    checks = []
    def add(name, ok, detail):
        checks.append(dict(name=name, ok=bool(ok), detail=detail))
    origin = urlsplit(env.get('MEDIA_PUBLIC_ORIGIN', ''))
    add('HTTPS 주소', origin.scheme == 'https' and bool(origin.hostname) and
        'REPLACE' not in origin.netloc and not origin.username and not origin.password and
        origin.path in ('', '/') and not origin.query and not origin.fragment,
        '실제 HTTPS 주소를 MEDIA_PUBLIC_ORIGIN에 등록')
    password = Path(env.get('MEDIA_ACCESS_PASSWORD_FILE', '/nonexistent'))
    try:
        private = password.stat().st_mode & 0o077 == 0
        valid = len(password.read_text().strip()) >= 16
    except OSError:
        private = valid = False
    add('접속 암호', private and valid, '16자 이상 암호 파일, 소유자만 접근 가능')
    for module in ('pptx', 'pymupdf', 'olefile', 'pypdf', 'reportlab',
                   'msal', 'cryptography', 'requests', 'imageio_ffmpeg'):
        add('Python '+module, importlib.util.find_spec(module) is not None, '제작 의존성 설치')
    for name in ('soffice', 'pdftoppm', 'fc-match'):
        add(name, shutil.which(name) is not None, '서버 실행 계정 PATH에서 접근 가능')
    templates = Path(env.get('MEDIA_WORSHIP_TEMPLATES', str(root/'assets/worship')))
    for service in ('sunday', 'wednesday', 'friday-zoom', 'friday-in-person'):
        add(service+' 시작 템플릿', (templates/(service+'-start.pptx')).is_file(), '검수된 원본 템플릿 설치')
    for name in ('original-design.pdf', 'original-regular.ttf', 'original-bold.ttf'):
        add('주보 '+name, (root/'assets/private/bulletin'/name).is_file(), '비공개 기존 주보 디자인 설치')
    for group in ('gyeonggi', 'nanum'):
        add(group+' 글꼴 파일', any((root/'assets/fonts'/group).glob('*.ttf')) or any((root/'assets/fonts'/group).glob('*.otf')), '파일 확인 후 시스템 글꼴 등록·렌더링 검수 필요')
    add('이름·직분 명단', (root/'data/private/people.json').is_file(), '사용자가 확인한 명단 비공개 설치')
    add('성경 자료', (root/'data/private/bible_fixed.json').is_file() or any((root/'data/private/bible_sources').glob('*.json')), '검수된 개역개정 자료 비공개 설치')
    parent = database.parent
    add('영구 저장소 쓰기', parent.is_dir() and os.access(parent, os.W_OK), '서비스 계정으로 실행해 확인')
    return dict(ready=all(c['ok'] for c in checks), checks=checks,
                remaining_live_checks=['실제 HTTPS·외부 접속', '서버 PPT/PDF 렌더링', '백업 복구', '팀원 컴퓨터와 Zoom 음성 공유'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--database', type=Path, required=True)
    args = parser.parse_args()
    report = check_deployment(args.root, args.database)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['ready'] else 1)


if __name__ == '__main__':
    main()
