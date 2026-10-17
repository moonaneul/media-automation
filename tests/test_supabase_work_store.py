from unittest.mock import Mock, patch

import pytest
import requests

from media_automation.cloud.supabase_auth import AccessDenied
from media_automation.cloud.supabase_work_store import SupabaseWorkStore, WorkStoreUnavailable
from media_automation.web.original.work_store import RevisionConflict

DAY = '2026-10-14'
DATA = {'fields': {'설교 제목': {'state': 'VALUE', 'value': '이번 주 제공 제목'}}}


def store():
    return SupabaseWorkStore('https://example.supabase.co', 'sb_publishable_test', 'private-token')


def response(data, status=200):
    return Mock(status_code=status, json=Mock(return_value=data))


def test_empty_week_does_not_inherit_previous_values():
    with patch('media_automation.cloud.supabase_work_store.requests.request',
               return_value=response({'revision': 0, 'data': {}, 'updated_at': None})):
        assert store().get(DAY, 'sunday')['data'] == {}


def test_save_uses_atomic_rpc_and_user_token():
    current = {'revision': 5, 'data': DATA, 'updated_at': '2026-10-14T01:00:00Z'}
    with patch('media_automation.cloud.supabase_work_store.requests.request',
               return_value=response({'saved': True, 'current': current})) as call:
        assert store().save(DAY, 'wednesday', 4, DATA) == current
        assert call.call_count == 1
        assert call.call_args.args[0] == 'POST'
        assert call.call_args.args[1].endswith('/rpc/media_save_work')
        assert call.call_args.kwargs['json']['p_expected_revision'] == 4
        assert call.call_args.kwargs['headers']['Authorization'] == 'Bearer private-token'
        assert call.call_args.kwargs['allow_redirects'] is False


def test_conflict_preserves_latest_input_for_caller():
    current = {'revision': 6, 'data': {'fields': {}}, 'updated_at': '2026-10-14T01:00:00Z'}
    with patch('media_automation.cloud.supabase_work_store.requests.request',
               return_value=response({'saved': False, 'current': current})) as call:
        with pytest.raises(RevisionConflict) as exc:
            store().save(DAY, 'wednesday', 4, DATA)
        assert exc.value.current == current
        assert call.call_count == 1


def test_timed_out_write_is_not_retried_and_does_not_expose_token():
    with patch('media_automation.cloud.supabase_work_store.requests.request',
               side_effect=requests.Timeout('private-token')) as call:
        with pytest.raises(WorkStoreUnavailable) as exc:
            store().save(DAY, 'wednesday', 0, DATA)
        assert 'private-token' not in str(exc.value)
        assert call.call_count == 1


@pytest.mark.parametrize('status,error', [(401, AccessDenied), (403, AccessDenied),
                                         (302, WorkStoreUnavailable), (500, WorkStoreUnavailable)])
def test_permission_or_backend_failure_cannot_be_empty_week(status, error):
    with patch('media_automation.cloud.supabase_work_store.requests.request',
               return_value=response({}, status)):
        with pytest.raises(error):
            store().get(DAY, 'wednesday')


@pytest.mark.parametrize('revision,data', [(True, DATA), (-1, DATA), (0, None),
    (0, {'fields': {'text': {'state': 'NONE', 'value': 'past week'}}}),
    (0, {'fields': {'text': {'state': 'VALUE', 'value': ''}}}),
    (0, {'fields': {'text': {'state': 'UNSET', 'value': 'past week'}}}),
    (0, {'fields': []}), (0, {'value': float('nan')})])
def test_invalid_data_never_reaches_server(revision, data):
    with patch('media_automation.cloud.supabase_work_store.requests.request') as call:
        with pytest.raises(ValueError):
            store().save(DAY, 'wednesday', revision, data)
        call.assert_not_called()


@pytest.mark.parametrize('current', [{'revision': 9, 'data': DATA, 'updated_at': None},
                                   {'revision': 1, 'data': {}, 'updated_at': None}])
def test_unexpected_save_response_is_not_success(current):
    with patch('media_automation.cloud.supabase_work_store.requests.request',
               return_value=response({'saved': True, 'current': current})):
        with pytest.raises(WorkStoreUnavailable):
            store().save(DAY, 'wednesday', 0, DATA)
