"""Cloud Run HTTP entrypoint. Hosted state never falls back to SQLite."""
import os
from types import SimpleNamespace

from .dispatcher import Dispatcher
from .http import Hosted
from .job_api import JobBackend
from .sessions import Sessions
from .supabase_auth import SupabaseAuth
from .worker import runtime_connection
from ..web.original.server import make_server


def main():
    url, secret, key, cloud = runtime_connection()
    auth = SupabaseAuth(url, os.environ['MEDIA_SUPABASE_PUBLISHABLE_KEY'])
    backend = JobBackend(url, secret)
    hosted = Hosted(auth, Sessions(url, secret, key.encode()), cloud, backend,
                    Dispatcher(os.environ['MEDIA_WORKER_RESOURCE'], backend))
    port = int(os.environ.get('PORT', '8080'))
    if not 1 <= port <= 65535:
        raise ValueError('Invalid PORT')
    server = make_server(SimpleNamespace(path='/tmp/unused-hosted.db'), port=port,
        bind_host='0.0.0.0', public_origin=os.environ['MEDIA_PUBLIC_ORIGIN'],
        supabase_auth=auth, hosted=hosted)
    print('Hosted media server ready', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
