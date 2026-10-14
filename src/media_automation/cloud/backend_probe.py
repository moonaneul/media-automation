"""Check server-only Supabase access and encrypted OneDrive persistence."""
import json
import os
from types import SimpleNamespace

import requests

from .encrypted_connection import EncryptedConnection
from .runtime_secrets import load_secret
from .secret_connection import SecretConnection
from .supabase_auth import SupabaseAuth
from ..web.original.onedrive import OneDrive


def inspect_backend():
    checks={'supabase_access':False,'encrypted_connection':False,'source_access':False,
            'archive_access':False,'anonymous_connection_blocked':False,'ready':False}
    stage='configuration'
    try:
        project=os.environ.get('MEDIA_GCP_PROJECT','church-media-511519')
        url=os.environ.get('MEDIA_SUPABASE_URL','https://rzqvhldujuaeqnckxezw.supabase.co')
        publishable=os.environ.get('MEDIA_SUPABASE_PUBLISHABLE_KEY','sb_publishable_038LJ1Y5eNWnMkzrbR4Pwg_ogJOxxt5')
        url=SupabaseAuth(url,publishable).url
        stage='server_credentials'
        key=load_secret(f'projects/{project}/secrets/church-media-supabase')
        cipher=load_secret(f'projects/{project}/secrets/church-media-onedrive-key',version='1')
        if not key.startswith('sb_secret_'):raise ValueError('Server key required')
        stage='supabase'
        response=requests.get(url+'/rest/v1/media_songs',params={'select':'id','limit':'1'},
                              headers={'apikey':key},timeout=(5,15),allow_redirects=False)
        if response.status_code!=200:raise ValueError('Backend access denied')
        checks['supabase_access']=True
        stage='encrypted_connection'
        resource=f'projects/{project}/secrets/church-media-onedrive'
        backend=EncryptedConnection(url,key,cipher.encode(),bootstrap=lambda:SecretConnection(resource).read())
        backend.read()
        checks['encrypted_connection']=True
        cloud=OneDrive(SimpleNamespace(path='/tmp/backend-probe-unused.db'),connection_backend=backend)
        for purpose in ('source','archive'):
            stage=purpose
            item=cloud.item(cloud.selected(purpose)['id'])
            if 'folder' not in item:raise ValueError('Expected folder')
            checks[purpose+'_access']=True
        stage='anonymous_access'
        response=requests.get(url+'/rest/v1/media_connections',params={'select':'id','limit':'1'},
                              headers={'apikey':publishable},timeout=(5,15),allow_redirects=False)
        checks['anonymous_connection_blocked']=response.status_code in (401,403)
        if not checks['anonymous_connection_blocked']:raise ValueError('Private access check failed')
        checks['ready']=True
    except Exception:
        checks['failed_stage']=stage
    return checks


def main():
    checks=inspect_backend()
    print(json.dumps(checks))
    return 0 if checks['ready'] else 1


if __name__=='__main__':raise SystemExit(main())
