"""Use a frozen cloud input with the existing production engine in a temp store."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile

from ..web.original.work_store import WorkStore


RUNTIME_ROOTS = ('assets/worship/', 'assets/private/friday_reference/',
                 'assets/private/friday_zoom/', 'assets/private/bulletin/', 'data/private/bible_sources/')


def validate_runtime_path(value):
    if not isinstance(value, str):
        raise ValueError('Invalid runtime path')
    path = PurePosixPath(value)
    if (path.is_absolute() or '..' in path.parts or '\\' in value
            or path.as_posix() != value or not (
                value == 'data/private/bible_fixed.json' or any(value.startswith(p) for p in RUNTIME_ROOTS))):
        raise ValueError('Invalid runtime path')
    return path


class SnapshotStore(WorkStore):
    def __init__(self, path, snapshot, cloud):
        super().__init__(path)
        self.cloud = cloud
        self.file_records = {}
        tables = snapshot['tables']
        for row in tables['files']:
            digest = row['digest']
            if not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest):
                raise ValueError('Invalid cloud original digest')
            if digest in self.file_records:
                raise ValueError('Duplicate cloud original digest')
            self.file_records[digest] = row
        day, service = snapshot['day'], snapshot['service']
        self.validate(day, service)
        work = snapshot['work']
        if type(work['revision']) is not int or work['revision'] < 1 or not isinstance(work['data'], dict):
            raise ValueError('Save the work before production')
        with self.connect() as db:
            db.execute('insert into works values(?,?,?,?,?)',
                       (day, service, work['revision'], json.dumps(work['data'], ensure_ascii=False), work['updated_at']))
            for row in tables['songs']:
                db.execute('insert into songs values(?,?)', (row['id'], json.dumps(row['payload'], ensure_ascii=False)))
            for row in tables['song_assets']:
                db.execute('insert into song_assets values(?,?,?)', (row['song_id'], row['digest'], row['filename']))
            for row in tables['reviews']:
                db.execute('insert into asset_reviews values(?,?,?)',
                           (row['song_id'], row['digest'], json.dumps(row['payload'], ensure_ascii=False)))
            for row in tables['attachments']:
                if row['day'] != day or row['service'] != service:
                    raise ValueError('Attachment belongs to another work')
                db.execute('insert into attachments values(?,?,?,?,?)',
                           (day, service, row['slot'], row['filename'], row['digest']))
            db.execute('create table bulletin_settings(id integer primary key,revision integer,payload text)')
            for row in tables['settings']:
                db.execute('insert into bulletin_settings values(?,?,?)',
                           (row['id'], row['revision'], json.dumps(row['payload'], ensure_ascii=False)))
        references = [r['digest'] for r in [*tables['attachments'], *tables['song_assets']]]
        if any(d not in self.file_records for d in references):
            raise ValueError('Cloud original reference missing')

    def ensure_original(self, digest):
        row = self.file_records.get(digest)
        if row is None:
            raise ValueError('Unregistered cloud original')
        target = Path(self.path).with_suffix('.files') / digest
        if target.is_file():
            return target
        if type(row.get('size')) is not int or not 0 < row['size'] <= 128 * 1024 * 1024:
            raise ValueError('Cloud original exceeds size limit')
        if sum(p.stat().st_size for p in target.parent.glob('*') if p.is_file()) + row['size'] > 768 * 1024 * 1024:
            raise ValueError('Production originals exceed total size limit')
        item = self.cloud.item(row['item_id'])
        if (item.get('size') != row['size'] or 'file' not in item
                or item.get('parentReference', {}).get('driveId') != row['drive_id']
                or not self.cloud.within(item, self.cloud.selected('source'))):
            raise ValueError('Cloud original location/type/size changed')
        data = self.cloud._download(item)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Cloud original hash differs')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    def original(self, digest):
        self.ensure_original(digest)
        return super().original(digest)

    def attachments(self, day, service):
        self.validate(day, service)
        with self.connect() as db:
            rows = db.execute('select slot,filename,digest from attachments where day=? and service=?', (day, service)).fetchall()
        return [{'slot': slot, 'filename': name, 'digest': digest, 'archive_status': 'cloud_source'}
                for slot, name, digest in rows]


@contextmanager
def materialize(snapshot, cloud, output):
    if output not in ('ppt', 'pdf'):
        raise ValueError('Invalid production output')
    with tempfile.TemporaryDirectory(prefix='media-cloud-job-') as folder:
        root = Path(folder)
        store = SnapshotStore(root / 'work.db', snapshot, cloud)
        service = snapshot['service']
        zoom = service == 'friday' and snapshot['work']['data'].get('fridayMode', 'zoom') == 'zoom'
        assets = snapshot['tables']['runtime_assets']
        for row in assets:
            validate_runtime_path(row['path'])
        names = {r['path']: r for r in assets}
        if output == 'pdf' and (service != 'sunday' or len(snapshot['tables']['settings']) != 1):
            raise ValueError('Confirmed bulletin settings required')
        if output == 'pdf':
            for name in ('original-design.pdf', 'original-regular.ttf', 'original-bold.ttf'):
                relative = 'assets/private/bulletin/' + name
                if relative not in names:
                    raise ValueError('Required original bulletin design/fonts missing')
                row = names[relative]
                target = root / validate_runtime_path(relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(store.ensure_original(row['digest']), target)
        if output == 'ppt':
            start = 'friday-zoom' if zoom else 'friday-in-person' if service == 'friday' else service
            required = 'assets/worship/' + start + '-start.pptx'
            if required not in names or 'data/private/bible_fixed.json' not in names:
                raise ValueError('Required design/Bible runtime assets missing')
            if zoom and any('assets/private/friday_reference/' + n + '.pptx' not in names
                            for n in ('cover', 'bible', 'sermon', 'prayer', 'word-prayer', 'community-prayer', 'personal')):
                raise ValueError('Friday reference designs missing')
            selected = [r for r in assets if r['path'] == required or r['path'].startswith('data/private/')
                        or zoom and r['path'].startswith('assets/private/')]
            for row in selected:
                source = store.ensure_original(row['digest'])
                target = root / validate_runtime_path(row['path'])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        variables = {'MEDIA_BULLETIN_ASSETS': root / 'assets/private/bulletin',
                     'MEDIA_WORSHIP_TEMPLATES': root / 'assets/worship',
                     'MEDIA_BIBLE_SOURCES': root / 'data/private/bible_sources',
                     'MEDIA_BIBLE_FILE': root / 'data/private/bible_fixed.json',
                     'MEDIA_FRIDAY_REFERENCE': root / 'assets/private/friday_reference',
                     'MEDIA_FRIDAY_MUSIC': root / 'assets/private/friday_zoom'}
        previous = {k: os.environ.get(k) for k in variables}
        try:
            os.environ.update({k: str(v) for k, v in variables.items()})
            yield store
        finally:
            for key, value in previous.items():
                if value is None: os.environ.pop(key, None)
                else: os.environ[key] = value
