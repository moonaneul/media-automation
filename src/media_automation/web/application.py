from __future__ import annotations

import json
import threading
from pathlib import Path
from tempfile import NamedTemporaryFile
from media_automation.production.jobs import ProductionJobs, inside

ALLOWED = {'.yaml', '.yml', '.json', '.txt', '.hwp', '.ppt', '.pptx', '.pdf', '.png', '.jpg', '.jpeg', '.mp3', '.mp4', '.ttf'}


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
            return record

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
            workspace = self.jobs._directory(job_id) / 'workspace'
            if record['service'] in {'sunday', 'wednesday'}:
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
