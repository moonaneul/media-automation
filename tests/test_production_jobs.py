from pathlib import Path
import json
import pytest
from media_automation.production.jobs import ProductionJobs


def engine(tmp_path):
    repo = tmp_path/'repo'
    repo.mkdir()
    program = "from pathlib import Path\np=Path('output/result.pdf');p.parent.mkdir(exist_ok=True);p.write_bytes(b'%PDF-test')\n"
    for name in ('wednesday','sunday','friday','bulletin'):
        (repo/f'{name}.py').write_text(program)
    return ProductionJobs(repo,tmp_path/'jobs')


def test_jobs_do_not_inherit_previous_week_and_are_isolated(tmp_path):
    jobs = engine(tmp_path)
    (jobs.repository/'output').mkdir()
    (jobs.repository/'output/old.pdf').write_bytes(b'old')
    first = jobs.create('friday','2026-10-09')
    second = jobs.create('friday','2026-10-09')
    assert first != second
    result = jobs.run(first)
    assert result.state == 'generated'
    assert result.artifacts == ('output/result.pdf',)
    assert not (jobs.jobs_root/second/'workspace/output').exists()
    assert (jobs.repository/'output/old.pdf').read_bytes() == b'old'
    # Existing identical files cannot be presented as a freshly generated deck.
    (jobs.jobs_root/first/'workspace/friday.py').write_text('pass\n')
    assert jobs.run(first).state == 'failed'


def test_failed_command_does_not_publish_partial_artifacts(tmp_path):
    jobs = engine(tmp_path)
    (jobs.repository/'friday.py').write_text("from pathlib import Path\np=Path('output/partial.pptx');p.parent.mkdir();p.write_bytes(b'partial')\nraise SystemExit(2)\n")
    job = jobs.create('friday','2026-10-09')
    result = jobs.run(job)
    assert result.state == 'failed'
    assert result.returncode == 2
    assert result.artifacts == ()
    # Failure may leave files for diagnostics, but state never implies success.
    assert json.loads((jobs.jobs_root/job/'job.json').read_text())['state'] == 'failed'


def test_staging_rejects_escape_overwrite_and_code_upload(tmp_path):
    jobs = engine(tmp_path)
    job = jobs.create('sunday','2026-09-27')
    source=tmp_path/'input.txt';source.write_text('latest')
    for target in ('../outside', '/tmp/outside', 'sunday.py'):
        with pytest.raises(ValueError):jobs.stage(job,source,target)
    jobs.stage(job,source,'input/notice.txt')
    with pytest.raises(FileExistsError):jobs.stage(job,source,'input/notice.txt')
    with pytest.raises(ValueError):jobs.run(job,source='../outside.pptx')
