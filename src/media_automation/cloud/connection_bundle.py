"""Passphrase-protected transfer of existing OneDrive credentials.

Only the encrypted file crosses machines. Do not put it in a container image or
Git. Decryption is intended for a trusted import process, not the web API.
"""
import base64
import json
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERATIONS = 600000
MAX_BUNDLE_BYTES = 128 * 1024


def _cipher(passphrase, salt):
    if not isinstance(passphrase, str) or len(passphrase) < 16:
        raise ValueError('전달용 암호는 16자 이상으로 입력하세요.')
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(passphrase.encode())))


def encrypt_connection(connection, passphrase):
    if not isinstance(connection, dict) or not connection.get('account') or not connection.get('secret'):
        raise ValueError('연결된 OneDrive 계정이 필요합니다.')
    data = json.dumps(connection, ensure_ascii=False, allow_nan=False).encode()
    if len(data) > 64 * 1024:
        raise ValueError('연결 정보 크기가 한도를 초과했습니다.')
    salt = os.urandom(16)
    token = _cipher(passphrase, salt).encrypt(data).decode()
    return json.dumps({'format': 'church-media-onedrive-v1', 'salt': base64.b64encode(salt).decode(),
                       'token': token}, separators=(',', ':')).encode()


def decrypt_connection(bundle, passphrase):
    if not isinstance(bundle, bytes) or len(bundle) > MAX_BUNDLE_BYTES:
        raise ValueError('암호화 파일의 크기를 확인하세요.')
    try:
        envelope = json.loads(bundle)
        if envelope['format'] != 'church-media-onedrive-v1':
            raise ValueError()
        salt = base64.b64decode(envelope['salt'], validate=True)
        if len(salt) != 16:
            raise ValueError()
        data = json.loads(_cipher(passphrase, salt).decrypt(envelope['token'].encode()))
        if not isinstance(data, dict) or not data.get('account') or not data.get('secret'):
            raise ValueError()
        return data
    except (ValueError, KeyError, TypeError, AttributeError, InvalidToken, UnicodeError):
        raise ValueError('전달용 암호 또는 암호화 파일을 확인하세요.') from None
