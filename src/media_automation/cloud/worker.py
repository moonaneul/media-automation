"""One claimed, frozen production request per Cloud Run execution."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from .artifacts import upload_verified
from .encrypted_connection import EncryptedConnection
from .job_api import JobBackend
from .runtime_secrets import load_secret
from .snapshot import materialize
from ..web.original.onedrive import OneDrive


def runtime_connection():
    project = os.environ.get('MEDIA_GCP_PROJECT', 'church-media-511519')
    url = os.environ['MEDIA_SUPABASE_URL']
    secret = load_secret(f'projects/{project}/secrets/church-media-supabase')
    key = load_secret(f'projects/{project}/secrets/church-media-onedrive-key', '1')
    # Bootstrap was verified already; a missing encrypted row now fails closed.
    connection = EncryptedConnection(url, secret, key.encode())
    cloud = OneDrive(SimpleNamespace(path='/tmp/cloud-unused.db'), connection_backend=connection)
    return url, secret, key, cloud


def render_artifact(path, output, result):
    import pymupdf
    from ..web.pptx_preview import convert_pptx
    pdf = path if output == 'pdf' else path.with_suffix('.preview.pdf')
    renderer = 'pdf' if output == 'pdf' else convert_pptx(path, pdf)
    with pymupdf.open(pdf) as doc:
        expected = 2 if output == 'pdf' else result['slide_count']
        if len(doc) != expected or not 0 < expected <= 500:
            raise ValueError('Rendered page count differs')
        for page in doc:
            if output == 'pdf' and (abs(page.rect.width - 841.89) > 2 or abs(page.rect.height - 595.28) > 2):
                raise ValueError('Bulletin must be two landscape A4 sides')
            page.get_pixmap(matrix=pymupdf.Matrix(.5, .5), alpha=False)
    return pdf, {'rendered': True, 'page_count': expected, 'renderer': renderer,
                 'visual_review_pending': True, 'actual_playback_verified': False}


def execute(identifier, execution, backend, cloud, render=render_artifact):
    identifier = str(UUID(identifier))
    claimed = backend.claim(identifier, execution)
    if not isinstance(claimed, dict) or claimed.get('claimed') is not True:
        return {'claimed': False}
    if claimed.get('id') != identifier:
        raise ValueError('Claim identity differs')
    def checkpoint():
        active = backend.call('media_job_active', {'p_id': identifier, 'p_execution': execution})
        if not isinstance(active, dict) or active.get('active') is not True:
            raise ValueError('Production cancelled, expired or access revoked')
    stage = 'snapshot'
    try:
        checkpoint()
        output = claimed['output']
        snapshot = claimed['snapshot']
        with materialize(snapshot, cloud, output) as store:
            from ..web.original.generation import generate
            from ..web.original.bulletin_generation import generate_bulletin
            body = {'date': snapshot['day'], 'service': snapshot['service'],
                    'revision': snapshot['work']['revision'], 'groups': claimed['groups'], 'output': output}
            stage = 'generation'
            result = (generate_bulletin if output == 'pdf' else generate)(store, body)
            directory = Path(store.path).with_suffix('.generated')
            path = directory / (result['file_id'] + ('.pdf' if output == 'pdf' else '.pptx'))
            checkpoint()
            stage = 'render'
            pdf, verification = render(path, output, result)
            stage = 'upload'
            # Use the same per-service folders as local archived outputs.
            folder = cloud.archive_destination(snapshot['service'], output)
            prefix = snapshot['day'] + '-' + snapshot['service'] + '-' + UUID(identifier).hex
            artifact = upload_verified(cloud, path, folder, prefix + path.suffix, checkpoint=checkpoint)
            preview = artifact if pdf == path else upload_verified(cloud, pdf, folder, prefix + '.preview.pdf', checkpoint=checkpoint)
            report_path = directory / (result['file_id'] + '.json')
            report = json.loads(report_path.read_text())
            report['verification'] = verification
            report['catalog_revision'] = snapshot['catalog_revision']
            report_path.write_text(json.dumps(report, ensure_ascii=False))
            report_record = upload_verified(cloud, report_path, folder, prefix + '.report.json', checkpoint=checkpoint)
            result.update(artifact=artifact, preview=preview, report=report_record, verification=verification,
                          complete=False, visual_review_pending=True, revision=body['revision'])
            stage = 'finish'
            checkpoint()
            finished = backend.finish(identifier, execution, True, result)
            if not isinstance(finished, dict) or finished.get('finished') is not True:
                raise ValueError('Completion rejected')
            return {'claimed': True, 'succeeded': True, 'id': identifier}
    except Exception:
        # Never log raw upstream errors or credentials; uncertain finish is not retried.
        if stage != 'finish':
            try:
                backend.finish(identifier, execution, False, {
                    'error': '제작을 완료하지 못했습니다. 입력과 자료를 확인한 뒤 다시 요청하세요.', 'stage': stage})
            except Exception:
                pass
        return {'claimed': True, 'succeeded': False, 'stage': stage}


def main():
    try:
        identifier = str(UUID(os.environ['MEDIA_JOB_ID']))
        execution = os.environ['CLOUD_RUN_EXECUTION']
        url, secret, _, cloud = runtime_connection()
        result = execute(identifier, execution, JobBackend(url, secret), cloud)
    except Exception:
        result = {'succeeded': False, 'stage': 'configuration'}
    print(json.dumps(result))
    return 0 if result.get('succeeded') or result.get('claimed') is False else 1


if __name__ == '__main__':
    raise SystemExit(main())
