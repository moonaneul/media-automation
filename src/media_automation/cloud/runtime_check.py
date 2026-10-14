"""Check the Linux production tools without loading church data or credentials."""
import importlib
import json
import platform
import shutil
import subprocess

MODULES = ('pptx', 'pypdf', 'fitz', 'yaml', 'olefile', 'reportlab', 'requests', 'msal', 'cryptography', 'google.cloud.secretmanager')
BINARIES = ('soffice', 'pdftoppm', 'ffmpeg', 'fc-match')


def inspect_runtime():
    modules = {}
    for name in MODULES:
        try:
            importlib.import_module(name)
            modules[name] = True
        except ImportError:
            modules[name] = False
    binaries = {name: bool(shutil.which(name)) for name in BINARIES}
    korean_font = False
    if binaries['fc-match']:
        result = subprocess.run(['fc-match', '-f', '%{family}', 'Noto Sans CJK KR'],
                                capture_output=True, text=True, timeout=10)
        korean_font = result.returncode == 0 and 'Noto Sans CJK' in result.stdout
    checks = {'linux': platform.system() == 'Linux', 'modules': modules,
              'binaries': binaries, 'korean_font': korean_font}
    checks['ready'] = checks['linux'] and all(modules.values()) and all(binaries.values()) and korean_font
    return checks


def main():
    result = inspect_runtime()
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
