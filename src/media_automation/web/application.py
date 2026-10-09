from __future__ import annotations

import json
import hashlib
import threading
from pathlib import Path
from tempfile import NamedTemporaryFile
from media_automation.production.jobs import ProductionJobs, inside
from .inputs import catalog, inspect_intake, next_revision_path, readiness, typed_path
from .notice_review import preview, confirmed_yaml
from .common_sunday import shared_paths, summary as sunday_summary

ALLOWED = {'.yaml', '.yml', '.json', '.txt', '.hwp', '.hwpx', '.ppt', '.pptx', '.pdf', '.png', '.jpg', '.jpeg', '.mp3', '.mp4', '.ttf'}


class Application:
    """Single local operator. Serializes mutations, runs one Mac production at a time."""
    def __init__(self, repository: Path, storage: Path):
        self.jobs = ProductionJobs(repository, storage)
        self.lock = threading.RLock()
        self.active: str | None = None

    def get(self, job_id: str) -> dict:
        with self.lock:
            directory = self.jobs._directory(job_id)
            record = json.loads((directory / 'job.json').read_text(encoding='utf-8'))
            workspace = directory / 'workspace'
            record['inputs'] = sorted(p.relative_to(workspace).as_posix()
                                      for name in ('input', 'data', 'sources', 'output')
                                      for p in (workspace / name).rglob('*') if p.is_file()
                                      and (name != 'output' or p.suffix.lower() in {'.yaml', '.yml', '.json'}))
            record['requirements'] = readiness(workspace, record['service'], record['date'])
            return record

    def catalog(self, job_id: str) -> list[dict]:
        return catalog(self.get(job_id)['service'])

    def upload_typed(self, job_id: str, kind: str, filename: str, content: bytes,
                     slot: str | None = None) -> dict:
        with self.lock:
            record = self.get(job_id)
            workspace = self.jobs._directory(job_id) / 'workspace'
            if kind == 'revision':
                if not any(item['kind'] == kind for item in catalog(record['service'])):
                    raise ValueError('이 작업에는 수정 안내 유형이 없습니다.')
                # Validate type and extension before assigning a new numbered instruction.
                if slot or Path(filename).suffix.lower() != '.txt' or not filename or Path(filename).name != filename:
                    raise ValueError('수정 안내는 .txt 파일만 등록할 수 있습니다.')
                relative = next_revision_path(workspace, record['service'], record['date'])
            else:
                relative = typed_path(record['service'], record['date'], kind, filename, slot)
            return self.upload(job_id, relative, content)

    def notice_preview(self, job_id: str) -> dict:
        with self.lock:
            record = self.get(job_id)
            directory = self.jobs._directory(job_id)
            draft = preview(directory / 'workspace', record['service'], record['date'])
            return {key: value for key, value in draft.items() if key != '_records'}

    def confirm_notice(self, job_id: str) -> dict:
        with self.lock:
            record = self.get(job_id)
            if record['service'] == 'bulletin':
                raise ValueError('주보는 주일 안내와 전달 주보를 별도로 검토합니다.')
            workspace = self.jobs._directory(job_id) / 'workspace'
            draft = preview(workspace, record['service'], record['date'])
            content = confirmed_yaml(draft)
            root = 'friday_zoom' if record['service'] == 'friday' else record['service']
            d = record['date'].replace('-', '')
            relative = f'output/{root}_intake/{root}_{d}_intake.yaml'
            if (workspace / relative).exists():
                raise FileExistsError('이미 안내 해석 YAML이 있습니다. 수정본은 새 작업에서 확정해주세요.')
            return self.upload(job_id, relative, content)

    def sunday_common_summary(self, job_id: str) -> dict:
        with self.lock:
            record = self.get(job_id)
            if record['service'] not in ('bulletin', 'sunday'):
                raise ValueError('주일 및 주보 작업에서만 공통 정보를 조회합니다.')
            workspace = self.jobs._directory(job_id) / 'workspace'
            return sunday_summary(workspace, record['date'])

    def import_sunday_week(self, bulletin_id: str, sunday_id: str) -> dict:
        """User-triggered copy of one *generated* Sunday job, never old weeks."""
        from media_automation.weekly_data.models import SundayData
        import yaml
        with self.lock:
            dest = self.get(bulletin_id)
            src = self.get(sunday_id)
            if dest['service'] != 'bulletin' or src['service'] != 'sunday':
                raise ValueError('주보 작업과 주일 작업을 선택해주세요.')
            if dest['date'] != src['date']:
                raise ValueError('서로 다른 주차의 데이터를 가져올 수 없습니다.')
            if src['state'] != 'generated':
                raise ValueError('주일 작업이 실제로 생성된 이후 공통 데이터를 가져올 수 있습니다.')
            if dest['state'] in {'queued','running','interrupted'} or self.active == bulletin_id:
                raise ValueError('실행 중이거나 중단된 주보 작업은 수정하지 않습니다.')
            src_workspace = self.jobs._directory(sunday_id) / 'workspace'
            dest_workspace = self.jobs._directory(bulletin_id) / 'workspace'
            paths = shared_paths(src['date'])
            loaded = {}
            # Validate every file before staging any of them.
            for kind, rel in paths.items():
                source = src_workspace / rel
                if not source.is_file():
                    raise ValueError(f'주일 작업에 {kind} 데이터가 없습니다. 기존 CLI를 확인해주세요.')
                if (dest_workspace / rel).exists():
                    raise FileExistsError(f'{kind} 자료가 이미 등록되어 있습니다. 덮어쓰지 않습니다.')
                raw = yaml.safe_load(source.read_text(encoding='utf-8-sig'))
                if not isinstance(raw, dict):
                    raise ValueError(f'{kind} 파일이 올바른 YAML이 아닙니다.')
                if kind == 'sunday_intake':
                    fields, issues = inspect_intake(source, src['date'], 'sunday')
                    if issues:
                        raise ValueError('주일 안내의 미해결 항목이 있습니다: ' + '; '.join(issues[:3]))
                else:
                    if raw.get('service') != 'sunday' or str(raw.get('date')) != src['date']:
                        raise ValueError(f'{kind} 주차가 이번 주와 일치하지 않습니다.')
                    SundayData.model_validate(raw)
                loaded[kind] = source
            common = sunday_summary(src_workspace, src['date'])
            if not common['consistent']:
                raise ValueError('주일 공통 데이터 불일치: ' + '; '.join(common['checks'][:3]))
            for source_kind, rel in paths.items():
                self.jobs.stage(bulletin_id, loaded[source_kind], rel)
            directory = self.jobs._directory(bulletin_id)
            record = json.loads((directory / 'job.json').read_text(encoding='utf-8'))
            record.update(state='needs_input', artifacts=[], review=None,
                          sunday_source_job_id=sunday_id,
                          sunday_source_sha256={kind: hashlib.sha256(source.read_bytes()).hexdigest()
                                                for kind, source in loaded.items()})
            self.jobs._save(directory, record)
            return self.get(bulletin_id)

    def set_bulletin_number(self, job_id: str, number: str) -> dict:
        import re
        import yaml
        with self.lock:
            record = self.get(job_id)
            if record['service'] != 'bulletin':
                raise ValueError('주보 작업에서만 호수를 입력할 수 있습니다.')
            number = number.strip().removeprefix('No.').strip()
            if not re.fullmatch(r'\d+-\d+', number):
                raise ValueError('주보 호수는 13-40 같은 형식으로 확인해주세요.')
            data = yaml.safe_dump({'date': record['date'], 'bulletin_number': number},
                                  allow_unicode=True, sort_keys=False).encode('utf-8')
            relative = f"input/bulletin/{record['date'].replace('-', '')}/state.yaml"
            return self.upload(job_id, relative, data)

    def list(self) -> list[dict]:
        with self.lock:
            return sorted((self.get(p.parent.name) for p in self.jobs.jobs_root.glob('*/job.json')),
                          key=lambda item: item['created_at'], reverse=True)

    def create(self, service: str, date: str) -> dict:
        with self.lock:
            return self.get(self.jobs.create(service, date))

    def upload(self, job_id: str, relative: str, content: bytes) -> dict:
        if Path(relative).suffix.lower() not in ALLOWED:
            raise ValueError('지원하지 않는 파일 형식입니다.')
        with self.lock:
            if self.active == job_id:
                raise ValueError('제작 중에는 자료를 변경할 수 없습니다.')
            # The low-level engine can stage explicit derived YAML under output;
            # the browser adapter never accepts old rendered PDFs/PPTs there.
            if Path(relative).parts and Path(relative).parts[0] == 'output' and Path(relative).suffix.lower() not in {'.yaml', '.yml', '.json'}:
                raise ValueError('output에는 명시적 입력 데이터만 등록할 수 있습니다.')
            with NamedTemporaryFile() as staged:
                staged.write(content)
                staged.flush()
                self.jobs.stage(job_id, Path(staged.name), relative)
            directory = self.jobs._directory(job_id)
            record = json.loads((directory / 'job.json').read_text())
            record.update(state='needs_input', artifacts=[], review=None)
            self.jobs._save(directory, record)
            return self.get(job_id)

    def start(self, job_id: str, source: str | None = None) -> dict:
        with self.lock:
            if self.active is not None:
                raise ValueError('다른 제작이 진행 중입니다. 완료 후 실행해주세요.')
            record = self.get(job_id)
            if record['state'] == 'interrupted':
                raise ValueError('중단된 작업은 새 작업으로 등록해주세요.')
            # Fail closed on explicit missing inputs or unresolved parse states.
            req = record['requirements']
            if not req['ready']:
                problems = req['missing'] + req['checks']
                raise ValueError('필수 자료와 안내 확인이 완료되지 않았습니다: ' + '; '.join(problems[:8]))
            workspace = self.jobs._directory(job_id) / 'workspace'
            if record['service'] in {'sunday', 'wednesday'}:
                source = source or f"input/{record['service']}/{record['date'].replace('-', '')}/source_rehearsal.pptx"
                if not source or Path(source).suffix.lower() != '.pptx' or not inside(workspace, source).is_file():
                    raise ValueError('등록된 이번 주 원본 PPTX를 선택해주세요.')
            record.update(state='queued', artifacts=[], review=None)
            record.pop('inputs', None)
            self.jobs._save(self.jobs._directory(job_id), record)
            self.active = job_id
            threading.Thread(target=self._run, args=(job_id, source), daemon=True).start()
            return self.get(job_id)

    def _run(self, job_id: str, source: str | None):
        try:
            self.jobs.run(job_id, source=source)
        except Exception:
            with self.lock:
                directory = self.jobs._directory(job_id)
                record = json.loads((directory / 'job.json').read_text())
                record.update(state='failed', artifacts=[], message='제작 실행 오류. 로컬 로그를 확인해주세요.')
                self.jobs._save(directory, record)
        finally:
            with self.lock:
                self.active = None

    def artifact(self, job_id: str, relative: str) -> Path:
        with self.lock:
            record = self.get(job_id)
            if record['state'] != 'generated' or relative not in record.get('artifacts', []):
                raise ValueError('현재 성공한 작업의 산출물만 받을 수 있습니다.')
            target = inside(self.jobs._directory(job_id) / 'workspace', relative)
            if not target.is_file():
                raise ValueError('결과 파일이 없습니다.')
            return target

    def recover(self):
        """Do not imply success after server interruption or silently resume an old task."""
        with self.lock:
            for p in self.jobs.jobs_root.glob('*/job.json'):
                record = json.loads(p.read_text())
                if record['state'] in {'queued', 'running'}:
                    record.update(state='interrupted', artifacts=[], message='서버가 중단되었습니다. 남은 제작 프로세스 종료를 확인하고 새 작업으로 등록해주세요.')
                    self.jobs._save(p.parent, record)
