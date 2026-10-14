from unittest.mock import Mock, patch

import pytest

from media_automation.cloud.job_api import JobBackend, JobClient
from media_automation.cloud.supabase_work_store import WorkStoreUnavailable
from media_automation.web.original.work_store import RevisionConflict

UID='776e30f7-9dd3-4229-b9d4-23de72331f21'


def client():return JobClient('https://example.supabase.co','sb_publishable_test','user-token')


def test_snapshot_conflict_does_not_mix_new_input_into_requested_revision():
    current={'revision':2,'data':{'fields':{}},'updated_at':None}
    with patch.object(JobClient,'_request',return_value={'matched':False,'current':current}):
        with pytest.raises(RevisionConflict) as error:client().snapshot('2026-10-14','wednesday',1)
        assert error.value.current==current


def test_busy_queue_is_returned_without_starting_another_job():
    with patch.object(JobClient,'_request',return_value={'queued':False,'busy':True}) as request:
        assert client().start('2026-10-14','wednesday',1,'ppt',[],UID)['busy']
        assert request.call_count==1


def test_invalid_job_response_cannot_be_success():
    with patch.object(JobClient,'_request',return_value={'queued':True,'id':'not-a-uuid','status':'queued'}):
        with pytest.raises(WorkStoreUnavailable):client().start('2026-10-14','wednesday',1,'ppt',[],UID)


def test_server_secret_goes_only_in_apikey_header_and_operation_is_restricted():
    response=Mock(status_code=200,json=Mock(return_value={'claimed':False}))
    with patch('media_automation.cloud.job_api.requests.post',return_value=response) as call:
        backend=JobBackend('https://example.supabase.co','sb_secret_private')
        assert backend.claim(UID,'execution')['claimed'] is False
        assert call.call_args.kwargs['headers']=={'apikey':'sb_secret_private'}
        with pytest.raises(ValueError):backend.call('arbitrary_sql',{})
        assert call.call_count==1
