"""Bounded, verified OneDrive transfers; never replace an existing output."""
import hashlib
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests

from ..web.original.onedrive import CloudError, valid_id

LIMIT = 512 * 1024 * 1024
CHUNK = 5 * 1024 * 1024


def digest_file(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def download_verified(cloud, record, target, purpose='archive'):
    size = record['size']
    if type(size) is not int or not 0 < size <= LIMIT:
        raise CloudError('파일 크기를 확인하세요.')
    item = cloud.item(record['item_id'])
    if ('file' not in item or item.get('size') != size
            or item.get('parentReference', {}).get('driveId') != record['drive_id']
            or not cloud.within(item, cloud.selected(purpose))):
        raise CloudError('보관 파일의 위치·크기가 변경됐습니다.')
    # Graph returns a short-lived Microsoft download URL; never persist it.
    url = item.get('@microsoft.graph.downloadUrl', '')
    parts = urlsplit(url)
    if (parts.scheme != 'https' or parts.username or parts.password
            or parts.port not in (None, 443) or not any(
                parts.hostname == d or (parts.hostname or '').endswith('.' + d)
                for d in ('1drv.com', 'onedrive.com', 'sharepoint.com', 'microsoftpersonalcontent.com'))):
        raise CloudError('Microsoft 다운로드 주소를 확인하지 못했습니다.')
    target = Path(target)
    if target.exists():
        raise FileExistsError('Download destination already exists')
    total = 0
    try:
        with cloud.http.get(url, stream=True, timeout=(10, 120), allow_redirects=False) as response:
            if response.status_code != 200:
                raise CloudError('보관 파일 다운로드에 실패했습니다.')
            with target.open('xb') as stream:
                for chunk in response.iter_content(1024 * 1024):
                    total += len(chunk)
                    if total > size:
                        raise CloudError('보관 파일 크기가 일치하지 않습니다.')
                    stream.write(chunk)
        if total != size or digest_file(target) != record['digest']:
            raise CloudError('보관 파일 검증에 실패했습니다.')
    except Exception:
        target.unlink(missing_ok=True)
        raise CloudError('보관 파일을 안전하게 내려받지 못했습니다.') from None
    return target


def upload_verified(cloud, path, folder, name, purpose='archive', checkpoint=lambda: None):
    path = Path(path)
    size = path.stat().st_size
    if not 0 < size <= LIMIT or Path(name).name != name or '\\' in name:
        raise CloudError('업로드 파일명·크기를 확인하세요.')
    checkpoint()
    digest = digest_file(path)
    session = cloud.graph('/me/drive/items/' + valid_id(folder['id']) + ':/'
                          + quote(name, safe='') + ':/createUploadSession', method='POST',
                          body={'item': {'@microsoft.graph.conflictBehavior': 'fail', 'name': name}})
    url = session.get('uploadUrl', '')
    parts = urlsplit(url)
    if (parts.scheme != 'https' or parts.username or parts.password or parts.port not in (None, 443)
            or not any(parts.hostname == d or (parts.hostname or '').endswith('.' + d)
                       for d in ('1drv.com', 'onedrive.com', 'sharepoint.com', 'microsoftpersonalcontent.com'))):
        raise CloudError('Microsoft 업로드 주소를 확인하지 못했습니다.')
    item = None
    with path.open('rb') as stream:
        for start in range(0, size, CHUNK):
            checkpoint()
            chunk = stream.read(CHUNK)
            try:
                response = cloud.http.put(url, data=chunk, timeout=(10, 120), allow_redirects=False,
                    headers={'Content-Range': f'bytes {start}-{start + len(chunk) - 1}/{size}'})
                if response.status_code in (200, 201) and start + len(chunk) == size:
                    item = response.json()
                elif response.status_code != 202 or start + len(chunk) == size:
                    raise CloudError('업로드 완료를 확인하지 못했습니다.')
            except (requests.RequestException, ValueError):
                raise CloudError('파일 업로드 결과를 확인하지 못했습니다.') from None
    if not isinstance(item, dict) or item.get('size') != size:
        raise CloudError('업로드 완료 파일의 크기를 확인하세요.')
    record = {'item_id': item['id'], 'drive_id': item['parentReference']['driveId'],
              'size': size, 'digest': digest, 'filename': name}
    checkpoint()
    verified = path.with_name(path.name + '.verified')
    try:
        download_verified(cloud, record, verified, purpose)
    finally:
        verified.unlink(missing_ok=True)
    return record
