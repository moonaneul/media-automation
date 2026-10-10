"""Shared work persistence core; not yet connected to the HTML or production engine."""
import json
import sqlite3
import uuid
import hashlib
from pathlib import Path
from datetime import date, datetime, timezone


class RevisionConflict(Exception):
    def __init__(self, current):
        self.current = current
        super().__init__('다른 기기에서 변경되었습니다. 최신 내용을 확인하세요.')


class WorkStore:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS works (date TEXT, service TEXT, revision INTEGER NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(date, service))')

            db.execute('CREATE TABLE IF NOT EXISTS songs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS asset_reviews (song_id TEXT, digest TEXT, payload TEXT NOT NULL, PRIMARY KEY(song_id,digest))')
            db.execute('CREATE TABLE IF NOT EXISTS song_assets (song_id TEXT, digest TEXT, filename TEXT, PRIMARY KEY(song_id,digest))')
            db.execute('CREATE TABLE IF NOT EXISTS attachments (day TEXT, service TEXT, slot TEXT, filename TEXT, digest TEXT, PRIMARY KEY(day,service,slot))')

    def attachments(self, day, service):
        self.validate(day, service)
        with self.connect() as db:
            rows=list(db.execute('SELECT slot,filename,digest FROM attachments WHERE day=? AND service=?', (day,service)))
        from ppt_conversion import conversion_status
        return [{'slot':r[0], 'filename':r[1], 'digest':r[2], 'archive_status':'pending_connection',**conversion_status(Path(self.path).with_suffix('.files')/r[2],r[1])} for r in rows]

    def attach(self, day, service, slot, filename, content, song_id=None):
        self.validate(day, service)
        if not slot or len(slot)>200 or not filename or len(filename)>255 or Path(filename).name != filename or '/' in filename or '\\' in filename:
            raise ValueError('파일명과 항목을 확인하세요.')
        if Path(filename).suffix.lower() not in ('.ppt', '.pptx', '.mp4', '.mp3', '.wav', '.pdf') or not content or len(content)>128*1024*1024:
            raise ValueError('지원 파일과 크기를 확인하세요.')
        if song_id:
            with self.connect() as db:
                if not db.execute('SELECT 1 FROM songs WHERE id=?',(song_id,)).fetchone():
                    raise ValueError('등록 곡을 확인하세요.')
        digest=hashlib.sha256(content).hexdigest()
        directory=Path(self.path).with_suffix('.files')
        directory.mkdir(parents=True,exist_ok=True)
        target=directory/digest
        existed=target.exists()
        if not existed:
            temporary=directory/(digest+'.'+uuid.uuid4().hex+'.tmp')
            try:
                temporary.write_bytes(content)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        with self.connect() as db:
            db.execute('INSERT INTO attachments VALUES (?,?,?,?,?) ON CONFLICT(day,service,slot) DO UPDATE SET filename=excluded.filename,digest=excluded.digest',(day,service,slot,filename,digest))
            if song_id:
                db.execute('INSERT OR IGNORE INTO song_assets VALUES (?,?,?)',(song_id,digest,filename))
        from ppt_conversion import conversion_status
        return {'slot':slot,'filename':filename,'digest':digest,'duplicate':existed,'archive_status':'pending_connection',**conversion_status(target,filename)}

    def songs(self):
        with self.connect() as db:
            songs=[json.loads(row[0]) for row in db.execute('SELECT payload FROM songs ORDER BY rowid')]
            for song in songs:
                song['assets']=[{'digest':r[0],'filename':r[1],'review_status':'unreviewed'} for r in db.execute('SELECT digest,filename FROM song_assets WHERE song_id=?',(song['id'],))]
            for song in songs:
                for asset in song['assets']:
                    row=db.execute('SELECT payload FROM asset_reviews WHERE song_id=? AND digest=?',(song['id'],asset['digest'])).fetchone()
                    asset['review']=json.loads(row[0]) if row else {'technical':False,'church':False,'permission':'unknown','note':''}
                    asset['eligible']=asset['review']['technical'] and asset['review']['church'] and asset['review']['permission']=='allowed'
            return songs

    def review_asset(self, song_id, digest, data):
        if type(data.get('technical')) is not bool or type(data.get('church')) is not bool or data.get('permission') not in ('unknown','allowed','not_allowed') or not isinstance(data.get('note',''),str) or len(data.get('note',''))>2000:
            raise ValueError('확인 상태를 점검하세요.')
        review={key:data.get(key,'') for key in ('technical','church','permission','note')}
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM song_assets WHERE song_id=? AND digest=?',(song_id,digest)).fetchone():
                raise ValueError('등록 원본을 확인하세요.')
            db.execute('INSERT INTO asset_reviews VALUES (?,?,?) ON CONFLICT(song_id,digest) DO UPDATE SET payload=excluded.payload',(song_id,digest,json.dumps(review,ensure_ascii=False)))
        return review

    def original(self, digest):
        if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('파일 식별값을 확인하세요.')
        with self.connect() as db:
            row=db.execute('SELECT filename FROM attachments WHERE digest=? UNION SELECT filename FROM song_assets WHERE digest=? LIMIT 1',(digest,digest)).fetchone()
        if not row:
            raise FileNotFoundError()
        return Path(self.path).with_suffix('.files')/digest, row[0]

    def register_song(self, data):
        title = data.get('title', '')
        aliases = data.get('aliases', [])
        edition = data.get('edition') or None
        number = data.get('number')
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise ValueError('곡명을 확인하세요.')
        if not isinstance(aliases, list) or len(aliases) > 20 or any(not isinstance(a, str) or len(a) > 200 for a in aliases):
            raise ValueError('별칭을 확인하세요.')
        if edition not in (None, 'new', 'old') or (edition and (type(number) is not int or not 1 <= number <= 999)) or (not edition and number is not None):
            raise ValueError('찬송가 종류와 번호를 확인하세요.')
        song = {'id': str(uuid.uuid4()), 'title': title.strip(), 'aliases': list(dict.fromkeys(a.strip() for a in aliases if a.strip())), 'edition': edition, 'number': number, 'assets': []}
        with self.connect() as db:
            db.execute('INSERT INTO songs VALUES (?,?)', (song['id'], json.dumps(song, ensure_ascii=False)))
        return song

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    @staticmethod
    def validate(day, service):
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError('날짜 형식을 확인하세요.')
        if service not in ('wednesday', 'friday', 'sunday'):
            raise ValueError('예배 종류를 확인하세요.')

    @staticmethod
    def decode(row):
        return {'revision': row[0], 'data': json.loads(row[1]), 'updated_at': row[2]} if row else {'revision': 0, 'data': {}, 'updated_at': None}

    def get(self, day, service):
        self.validate(day, service)
        with self.connect() as db:
            return self.decode(db.execute('SELECT revision,payload,updated_at FROM works WHERE date=? AND service=?', (day, service)).fetchone())

    def save(self, day, service, expected_revision, data):
        self.validate(day, service)
        if type(expected_revision) is not int or expected_revision < 0 or not isinstance(data, dict):
            raise ValueError('저장 요청 형식을 확인하세요.')
        fields = data.get('fields', {})
        if not isinstance(fields, dict):
            raise ValueError('입력 항목 형식을 확인하세요.')
        for field in fields.values():
            if not isinstance(field, dict) or field.get('state') not in ('UNSET', 'NONE', 'VALUE') or not isinstance(field.get('value', ''), str):
                raise ValueError('입력 상태를 확인하세요.')
            value = field.get('value', '')
            if (field['state'] == 'VALUE' and not value.strip()) or (field['state'] != 'VALUE' and value):
                raise ValueError('입력값과 상태가 일치하지 않습니다.')
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False)
        if len(payload.encode()) > 1024 * 1024:
            raise ValueError('입력 내용이 너무 큽니다.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = self.decode(db.execute('SELECT revision,payload,updated_at FROM works WHERE date=? AND service=?', (day, service)).fetchone())
            if current['revision'] != expected_revision:
                raise RevisionConflict(current)
            revision = expected_revision + 1
            updated = datetime.now(timezone.utc).isoformat()
            db.execute('INSERT INTO works VALUES (?,?,?,?,?) ON CONFLICT(date,service) DO UPDATE SET revision=excluded.revision,payload=excluded.payload,updated_at=excluded.updated_at', (day, service, revision, payload, updated))
            return {'revision': revision, 'data': json.loads(payload), 'updated_at': updated}
