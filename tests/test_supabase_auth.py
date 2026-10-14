from unittest.mock import Mock, patch

import pytest
import requests

from media_automation.cloud.supabase_auth import AccessDenied, AuthUnavailable, SupabaseAuth

UID = '776e30f7-9dd3-4229-b9d4-23de72331f21'


def response(data, status=200):
    return Mock(status_code=status, json=Mock(return_value=data))


def client():
    return SupabaseAuth('https://example.supabase.co', 'sb_publishable_test')


def test_verified_user_and_active_membership_required():
    with patch('media_automation.cloud.supabase_auth.requests.get', side_effect=[
        response({'id': UID, 'user_metadata': {'role': 'editor'}}),
        response([{'user_id': UID, 'role': 'admin', 'active': True}]),
    ]) as get:
        assert client().authenticate('Bearer token').role == 'admin'
        assert get.call_args.kwargs['headers']['Authorization'] == 'Bearer token'
        assert get.call_args.kwargs['params']['user_id'] == 'eq.' + UID
        assert get.call_args.kwargs['allow_redirects'] is False


@pytest.mark.parametrize('rows', [[], [{'user_id': UID, 'role': 'admin', 'active': False}],
    [{'user_id': UID, 'role': 'owner', 'active': True}],
    [{'user_id': 'another-user', 'role': 'admin', 'active': True}]])
def test_membership_denied(rows):
    with patch('media_automation.cloud.supabase_auth.requests.get', side_effect=[
        response({'id': UID, 'user_metadata': {'role': 'admin'}}), response(rows),
    ]):
        with pytest.raises(AccessDenied):
            client().authenticate('Bearer token')


@pytest.mark.parametrize('status', [401, 403])
def test_invalid_token_never_queries_membership(status):
    with patch('media_automation.cloud.supabase_auth.requests.get', return_value=response({}, status)) as get:
        with pytest.raises(AccessDenied):
            client().authenticate('Bearer expired')
        assert get.call_count == 1


@pytest.mark.parametrize('header', ['', 'Basic token', 'Bearer', 'Bearer x y', None])
def test_missing_token_does_not_call_backend(header):
    with patch('media_automation.cloud.supabase_auth.requests.get') as get:
        with pytest.raises(AccessDenied):
            client().authenticate(header)
        get.assert_not_called()


def test_network_failure_denies_access_without_exposing_token():
    with patch('media_automation.cloud.supabase_auth.requests.get', side_effect=requests.Timeout('secret-token')):
        with pytest.raises(AuthUnavailable) as exc:
            client().authenticate('Bearer secret-token')
        assert 'secret-token' not in str(exc.value)


@pytest.mark.parametrize('status', [302, 500])
def test_backend_failure_is_not_authorized(status):
    with patch('media_automation.cloud.supabase_auth.requests.get', return_value=response({}, status)):
        with pytest.raises(AuthUnavailable):
            client().authenticate('Bearer token')
