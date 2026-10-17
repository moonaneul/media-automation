"""Copy missing local originals to the selected OneDrive folder, never replace."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
from types import SimpleNamespace
import unicodedata
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from media_automation.web.original.onedrive import OneDrive, CloudError, public_item, valid_id


def digest_file(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verified_item(cloud, item, folder, expected_digest, size):
    if not item.get('id') or item.get('size') != size or not cloud.within(item, folder):
        raise CloudError('업로드 파일 위치 또는 크기 확인 실패')
    full = cloud.item(item['id'])
    actual = hashlib.sha256(cloud._download(full)).hexdigest()
    if actual != expected_digest:
        raise CloudError('OneDrive 원본 해시 불일치. 덮어쓰지 않았습니다.')
    return public_item(full)


def upload_new(cloud, folder, path, filename, digest):
    if not re.fullmatch(r'[a-f0-9]{64}', digest) or digest_file(path) != digest:
        raise ValueError('로컬 원본 해시 확인 실패')
    size = path.stat().st_size
    if not 0 < size <= 128 * 1024 * 1024:
        raise ValueError('원본 크기 확인 필요')
    source = Path(filename)
    name = unicodedata.normalize('NFC', source.stem)[:80] + '_' + digest + source.suffix
    existing = [item for item in cloud.children(folder['id']) if item.get('name') == name]
    if existing:
        if len(existing) != 1:
            raise CloudError('기존 동일 이름 원본 확인 필요')
        return verified_item(cloud, existing[0], folder, digest, size), False
    session = cloud.graph('/me/drive/items/' + valid_id(folder['id']) + ':/' + quote(name, safe='')
                          + ':/createUploadSession', method='POST',
                          body={'item': {'@microsoft.graph.conflictBehavior': 'fail', 'name': name}})
    url = session.get('uploadUrl', '')
    parts = urlsplit(url)
    domains = ('1drv.com', 'onedrive.com', 'sharepoint.com', 'microsoftpersonalcontent.com')
    if (parts.scheme != 'https' or parts.username or parts.password or parts.port not in (None, 443)
            or not any(parts.hostname == d or (parts.hostname or '').endswith('.' + d) for d in domains)):
        raise CloudError('Microsoft 업로드 주소 확인 실패')
    uploaded_hash = hashlib.sha256()
    with path.open('rb') as stream:
        for start in range(0, size, 5 * 1024 * 1024):
            chunk = stream.read(5 * 1024 * 1024)
            uploaded_hash.update(chunk)
            response = cloud.http.put(url, data=chunk,
                headers={'Content-Range': f'bytes {start}-{start + len(chunk) - 1}/{size}'},
                timeout=(10, 120), allow_redirects=False)
            final = start + len(chunk) == size
            if not final and response.status_code != 202:
                raise CloudError('원본 전송 중단. 완료 여부 확인 필요')
            if final:
                if response.status_code not in (200, 201) or uploaded_hash.hexdigest() != digest:
                    raise CloudError('원본 전송 완료 또는 내용 확인 실패')
                return verified_item(cloud, response.json(), folder, digest, size), True
    raise CloudError('원본 전송 완료 확인 실패')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    cloud = OneDrive(SimpleNamespace(path=str(args.database)))
    folder = cloud.selected('source')
    with sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        mapped = {r[0] for r in db.execute('select digest from cloud_song_sources')}
        rows = db.execute('select digest,filename from attachments union select digest,filename from song_assets order by digest,filename').fetchall()
    candidates = {}
    for digest, filename in rows:
        if digest not in mapped:
            candidates.setdefault(digest, filename)
    report = json.loads(args.report.read_text()) if args.report.exists() else {'files': [], 'errors': []}
    finished = {row['sha256'] for row in report['files']}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    for digest, filename in candidates.items():
        if digest in finished:
            continue
        try:
            item, created = upload_new(cloud, folder, args.database.with_suffix('.files') / digest, filename, digest)
            report['files'].append({'sha256': digest, 'filename': filename, 'item': item,
                                    'created': created, 'verified_sha256': True})
            print('확인 완료:', filename, flush=True)
        except Exception:
            report['errors'].append({'sha256': digest, 'filename': filename})
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print('전송 중단. 토큰·업로드 주소는 출력하지 않았습니다.', flush=True)
            return 1
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print('추가 원본 연결 확인:', len(report['files']), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
