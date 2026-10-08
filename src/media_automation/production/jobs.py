from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

SERVICES = {'wednesday', 'sunday', 'friday', 'bulletin'}


def inside(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or not path.parts or '..' in path.parts:
        raise ValueError('작업 내부의 상대 경로가 필요합니다.')
    target = root / path
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('작업 폴더 밖의 경로는 사용할 수 없습니다.')
    return target


@dataclass(frozen=True)
class JobResult:
    job_id: str
    service: str
    date: str
    state: str
    returncode: int | None
    artifacts: tuple[str, ...]
    log: str
    message: str


class ProductionJobs:
    """Isolates working files; not an OS security sandbox or public HTTP API."""
    def __init__(self, repository: Path, jobs_root: Path):
        self.repository = repository.resolve()
        self.jobs_root = jobs_root.resolve()

    def create(self, service: str, service_date: str) -> str:
        if service not in SERVICES:
            raise ValueError('지원하지 않는 예배 종류입니다.')
        if date.fromisoformat(service_date).isoformat() != service_date:
            raise ValueError('날짜는 YYYY-MM-DD 형식이어야 합니다.')
        job_id = uuid4().hex
        directory = self.jobs_root / job_id
        workspace = directory / 'workspace'
        workspace.mkdir(parents=True)
        # Copy code, never previous weekly data, media or output by default.
        for name in ('src', 'scripts'):
            source = self.repository / name
            if source.exists():
                shutil.copytree(source, workspace / name,
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for name in ('wednesday.py', 'sunday.py', 'friday.py', 'bulletin.py'):
            shutil.copy2(self.repository / name, workspace / name)
        design_assets = self.repository / 'assets/bulletin'
        if design_assets.is_dir():
            shutil.copytree(design_assets, workspace / 'assets/bulletin')
        self._save(directory, {'job_id':job_id, 'service':service,
                   'date':service_date, 'state':'needs_input', 'attempt':0,
                   'created_at':datetime.now(timezone.utc).isoformat()})
        return job_id

    def _directory(self, job_id: str) -> Path:
        if len(job_id) != 32 or any(c not in '0123456789abcdef' for c in job_id):
            raise ValueError('올바르지 않은 작업 ID입니다.')
        directory = self.jobs_root / job_id
        if not (directory / 'job.json').is_file():
            raise ValueError('작업을 찾을 수 없습니다.')
        return directory

    @staticmethod
    def _save(directory: Path, record: dict):
        staged = directory / 'job.json.tmp'
        staged.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        staged.replace(directory / 'job.json')

    def stage(self, job_id: str, source: Path, relative: str) -> Path:
        directory = self._directory(job_id)
        if (directory / 'running.lock').exists():
            raise RuntimeError('제작 중에는 입력을 변경할 수 없습니다.')
        destination = inside(directory / 'workspace', relative)
        if Path(relative).parts[0] not in {'input', 'assets', 'data', 'sources', 'output'}:
            raise ValueError('입력·자료 폴더에만 등록할 수 있습니다.')
        if destination.exists():
            raise FileExistsError('이미 등록된 파일입니다. 수정본은 새 작업으로 등록하세요.')
        if not source.is_file():
            raise FileNotFoundError(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination

    @staticmethod
    def _artifacts(workspace: Path) -> dict[str, tuple[str, int]]:
        result = {}
        for path in (workspace / 'output').rglob('*'):
            if path.is_file() and path.suffix.lower() in {'.pdf', '.pptx'}:
                result[path.relative_to(workspace).as_posix()] = (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
        return result

    def run(self, job_id: str, *, source: str | None = None, timeout: int = 600) -> JobResult:
        directory = self._directory(job_id)
        workspace = directory / 'workspace'
        record = json.loads((directory / 'job.json').read_text())
        service = record['service']
        command = [sys.executable, str(workspace / f'{service}.py'), 'complete', record['date']]
        if service in {'sunday', 'wednesday'}:
            if source is None or not inside(workspace, source).is_file():
                raise ValueError('해당 작업에 등록된 원본 PPT 경로가 필요합니다.')
            command.extend(([source] if service == 'sunday' else ['--source', source]))
        lock = directory / 'running.lock'
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError as exc:
            raise RuntimeError('이미 실행 중인 작업입니다.') from exc
        before = self._artifacts(workspace)
        record.update(state='running', attempt=record['attempt']+1)
        self._save(directory, record)
        log = directory / f"attempt-{record['attempt']}.log"
        env = dict(os.environ, PYTHONPATH=str(workspace / 'src'), PYTHONIOENCODING='utf-8')
        code = None
        try:
            with log.open('w', encoding='utf-8') as output:
                try:
                    completed = subprocess.run(command, cwd=workspace, env=env,
                                               stdout=output, stderr=subprocess.STDOUT,
                                               timeout=timeout, check=False)
                    code = completed.returncode
                    after = self._artifacts(workspace)
                    artifacts = tuple(name for name, digest in after.items() if before.get(name) != digest)
                    if code != 0:
                        artifacts = ()
                    state = 'generated' if code == 0 and artifacts else 'failed'
                    message = '생성 완료. 화면·재생 검수는 별도로 필요합니다.' if state == 'generated' else '입력 또는 제작 로그를 확인해주세요.'
                except subprocess.TimeoutExpired:
                    state, artifacts, message = 'failed', (), '제작 제한 시간을 초과했습니다.'
            result = JobResult(job_id, service, record['date'], state, code, artifacts, log.name, message)
            record.update(asdict(result))
            self._save(directory, record)
            return result
        except Exception:
            record.update(state='failed', message='제작 실행 중 오류가 발생했습니다.')
            self._save(directory, record)
            raise
        finally:
            lock.unlink(missing_ok=True)
