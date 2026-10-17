"""Create a code-only Cloud Shell upload, excluding all private/runtime files."""
import argparse
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    include=[ROOT/'pyproject.toml',ROOT/'deploy/cloud/Dockerfile.runtime',
             ROOT/'deploy/cloud/Dockerfile.runtime.dockerignore',ROOT/'deploy/cloud/build-runtime.yaml',ROOT/'deploy/cloud/deploy-runtime.sh']
    include += [p for p in (ROOT/'src').rglob('*') if p.is_file() and not p.is_symlink()
                and '__pycache__' not in p.parts and p.suffix in ('.py','.js','.html','.json')]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(args.output,'w:gz') as archive:
        for path in sorted(include):
            if path.is_symlink():raise ValueError('Symlink not allowed in cloud package')
            archive.add(path,arcname=path.relative_to(ROOT),recursive=False)
    print('Code-only runtime package:',args.output)

if __name__=='__main__':main()
