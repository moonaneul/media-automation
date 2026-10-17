"""Read fixed runtime credentials via the attached Google service account."""
import re


def load_secret(resource, version='latest', client=None):
    if (not isinstance(resource,str) or not re.fullmatch(r'projects/[a-z0-9][a-z0-9-]*[a-z0-9]/secrets/[A-Za-z0-9_-]+',resource)
            or not isinstance(version,str) or not re.fullmatch(r'latest|[1-9][0-9]*',version)):
        raise ValueError('Invalid runtime secret resource')
    if client is None:
        from google.cloud import secretmanager
        client=secretmanager.SecretManagerServiceClient()
    try:
        response=client.access_secret_version(request={'name':resource+'/versions/'+version},timeout=15,retry=None)
        return response.payload.data.decode().strip()
    except Exception:
        raise RuntimeError('Runtime credential could not be read') from None
