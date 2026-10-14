import json
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet
import pytest
import requests

from media_automation.cloud.encrypted_connection import EncryptedConnection
from media_automation.web.original.onedrive import CloudError

DATA={'client_id':'client','secret':'private-client-secret','cache':'private-refresh-token'}


def response(rows):return Mock(status_code=200,json=Mock(return_value=rows))


def test_only_ciphertext_is_sent_when_connection_is_updated():
    key=Fernet.generate_key();cipher=Fernet(key)
    initial={'revision':1,'ciphertext':cipher.encrypt(json.dumps(DATA).encode()).decode()}
    with patch('media_automation.cloud.encrypted_connection.requests.request',side_effect=[response([initial]),response([{'revision':2}])]) as call:
        backend=EncryptedConnection('https://example.supabase.co','sb_secret_private',key)
        assert backend.read()==DATA
        backend.write(DATA)
        args=call.call_args.kwargs
        assert args['params']['revision']=='eq.1'
        assert 'private-refresh-token' not in json.dumps(args['json'])
        assert 'Authorization' not in args['headers']
        assert json.loads(cipher.decrypt(args['json']['ciphertext'].encode()))==DATA


def test_concurrent_update_does_not_overwrite_current_connection():
    key=Fernet.generate_key();cipher=Fernet(key)
    row={'revision':1,'ciphertext':cipher.encrypt(json.dumps(DATA).encode()).decode()}
    with patch('media_automation.cloud.encrypted_connection.requests.request',side_effect=[response([row]),response([])]) as call:
        backend=EncryptedConnection('https://example.supabase.co','sb_secret_private',key)
        backend.read()
        with pytest.raises(CloudError):backend.write(DATA)
        assert call.call_count==2 and backend.revision==1


def test_bad_cipher_key_cannot_reset_stored_credentials_to_bootstrap():
    row={'revision':1,'ciphertext':Fernet(Fernet.generate_key()).encrypt(json.dumps(DATA).encode()).decode()}
    bootstrap=Mock(return_value=DATA)
    with patch('media_automation.cloud.encrypted_connection.requests.request',return_value=response([row])):
        backend=EncryptedConnection('https://example.supabase.co','sb_secret_private',Fernet.generate_key(),bootstrap)
        with pytest.raises(CloudError):backend.read()
        bootstrap.assert_not_called()


def test_network_error_does_not_print_keys_or_tokens():
    with patch('media_automation.cloud.encrypted_connection.requests.request',side_effect=requests.Timeout('private-token')):
        backend=EncryptedConnection('https://example.supabase.co','sb_secret_private',Fernet.generate_key())
        with pytest.raises(CloudError) as exc:backend.read()
        assert 'private-token' not in str(exc.value)
