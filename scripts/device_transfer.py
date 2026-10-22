"""Pack/verify/import local church inputs for Windows-to-Mac migration.

Non-destructive: excludes output, code, DB, tokens, and virtual environments.
Never overwrites an existing file; default import is dry-run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
import zipfile
from pathlib import Path, PurePosixPath

FOLDERS = ("sources", "input", "data/private", "assets/private")
MANIFEST = "__device_transfer_manifest__.json"
SCHEMA = "media-device-transfer-v1"
EXCLUDED_PARTS = {".git", ".venv", "venv", "work.onedrive", "__pycache__"}
EXCLUDED_ENDINGS = (".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm", ".pem", ".key")
LFS_HEADER = b"version https://git-lfs.github.com/spec/v1"


def sha256(stream):
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(chunk)
    return h.hexdigest()


def allowed(name):
    if not isinstance(name, str) or not name or name.startswith("/") or "\\" in name or ":" in name:
        return False
    p = PurePosixPath(name)
    if str(p) != name or any(part in ("", ".", "..") for part in name.split("/")):
        return False
    if not any(name.startswith(folder + "/") for folder in FOLDERS):
        return False
    if any(part.lower() in EXCLUDED_PARTS or part.lower().startswith(".env") for part in p.parts):
        return False
    return not name.lower().endswith(EXCLUDED_ENDINGS)


def collect(root):
    if not root.is_dir():
        raise ValueError("Source project not found")
    files = []
    for folder in FOLDERS:
        base = root / folder
        if not base.exists():
            continue
        if base.is_symlink():
            raise ValueError("Symlink input folder requires manual review")
        for current, subdirs, names in os.walk(base, followlinks=False):
            if any((Path(current) / d).is_symlink() for d in subdirs):
                raise ValueError("Symlink input subdirectory requires manual review")
            subdirs[:] = [d for d in subdirs if d.lower() not in EXCLUDED_PARTS]
            for name in names:
                src = Path(current) / name
                relative = src.relative_to(root).as_posix()
                if src.is_symlink() or not src.is_file():
                    raise ValueError("Symlink or special input file requires manual review")
                if not allowed(relative):
                    raise ValueError("Excluded input requires review: " + relative)
                size = src.stat().st_size
                if size <= 200 and src.read_bytes().startswith(LFS_HEADER):
                    raise ValueError("Git LFS pointer found; obtain real media first")
                with src.open("rb") as f:
                    digest = sha256(f)
                files.append({"path": relative, "size": size, "sha256": digest, "_source": src})
    files.sort(key=lambda rec: rec["path"])
    if len({r["path"].casefold() for r in files}) != len(files):
        raise ValueError("Case-insensitive path collision")
    return files


def pack(root, bundle):
    root = root.expanduser().resolve()
    bundle = bundle.expanduser().absolute()
    if root == bundle or root in bundle.parents:
        raise ValueError("Place transfer ZIP outside the source project")
    if bundle.exists() or not bundle.parent.is_dir():
        raise ValueError("ZIP already exists or its parent directory is missing")
    records = collect(root)
    if not records:
        raise ValueError("No input files found")
    manifest = {"schema": SCHEMA, "files": [
        {k: record[k] for k in ("path", "size", "sha256")} for record in records
    ]}
    temp = bundle.with_name(bundle.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED, compresslevel=5, allowZip64=True) as z:
            for rec in records:
                with rec["_source"].open("rb") as f, z.open(rec["path"], "w", force_zip64=True) as dest:
                    hash_obj = hashlib.sha256()
                    size = 0
                    for chunk in iter(lambda: f.read(1024 * 1024), b""):
                        dest.write(chunk)
                        hash_obj.update(chunk)
                        size += len(chunk)
                    if size != rec["size"] or hash_obj.hexdigest() != rec["sha256"]:
                        raise ValueError("Source changed during export: " + rec["path"])
            z.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=True, sort_keys=True))
        os.link(temp, bundle)  # exclusive creation; never overwrite an existing ZIP
    finally:
        temp.unlink(missing_ok=True)
    with bundle.open("rb") as f:
        zip_hash = sha256(f)
    return {"mode": "PACKED", "files": len(records),
            "bytes": sum(r["size"] for r in records), "zip_sha256": zip_hash,
            "originals_deleted": False}


def verify(bundle):
    if not bundle.is_file():
        raise ValueError("Transfer ZIP not found")
    with zipfile.ZipFile(bundle) as z:
        names = z.namelist()
        if len(set(names)) != len(names) or names.count(MANIFEST) != 1:
            raise ValueError("Duplicate or missing ZIP entry")
        if z.getinfo(MANIFEST).file_size > 10_000_000:
            raise ValueError("Transfer manifest too large")
        data = json.loads(z.read(MANIFEST))
        records = data.get("files")
        if data.get("schema") != SCHEMA or not isinstance(records, list):
            raise ValueError("Unexpected transfer manifest")
        expected = []
        for rec in records:
            if not isinstance(rec, dict):
                raise ValueError("Invalid record")
            name, size, digest = rec.get("path"), rec.get("size"), rec.get("sha256")
            if (not allowed(name) or type(size) is not int or size < 0
                    or not isinstance(digest, str) or len(digest) != 64
                    or any(c not in "0123456789abcdef" for c in digest)):
                raise ValueError("Unsafe transfer record")
            info = z.getinfo(name)
            if info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Archive includes a directory or symlink entry")
            if info.file_size != size:
                raise ValueError("Transfer size mismatch")
            with z.open(name) as f:
                if sha256(f) != digest:
                    raise ValueError("Transfer hash mismatch: " + name)
            expected.append(name)
        if (len({x.casefold() for x in expected}) != len(expected)
                or set(names) != set(expected) | {MANIFEST}):
            raise ValueError("Unexpected ZIP entry or duplicate filename")
    with bundle.open("rb") as f:
        zip_hash = sha256(f)
    return records, {"mode": "VERIFIED", "files": len(records), "zip_sha256": zip_hash}


def import_inputs(bundle, destination, *, copy=False):
    records, _ = verify(bundle)
    destination = destination.expanduser().resolve()
    if not destination.is_dir():
        raise ValueError("Destination directory must already exist")
    plan = []
    for rec in records:
        path = destination.joinpath(*rec["path"].split("/"))
        parents = [path] + list(path.parents)
        if any(p.is_symlink() for p in parents if p == destination or destination in p.parents):
            raise ValueError("Symlink in destination path")
        if path.exists() or path.is_symlink():
            if path.is_file() and path.stat().st_size == rec["size"]:
                with path.open("rb") as f:
                    same = sha256(f) == rec["sha256"]
            else:
                same = False
            status = "identical" if same else "conflict"
        else:
            status = "missing"
        plan.append((rec, path, status))
    result = {"mode": "COPY_MISSING_ONLY" if copy else "DRY_RUN",
              "files": len(plan), "copy_candidates": sum(s == "missing" for _, _, s in plan),
              "identical_files": sum(s == "identical" for _, _, s in plan),
              "conflicts": sum(s == "conflict" for _, _, s in plan), "copied": 0,
              "overwritten": False, "source_deleted": False}
    if copy:
        if result["conflicts"]:
            raise ValueError("Conflicting files: no copy performed; review before proceeding")
        with zipfile.ZipFile(bundle) as z:
            for rec, dest, status in plan:
                if status != "missing":
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists() or dest.is_symlink():
                    raise FileExistsError("Destination changed during transfer")
                temp = dest.with_name(dest.name + ".transfer-" + uuid.uuid4().hex)
                try:
                    with z.open(rec["path"]) as source, temp.open("xb") as target:
                        h = hashlib.sha256()
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            target.write(chunk)
                            h.update(chunk)
                    if h.hexdigest() != rec["sha256"]:
                        raise ValueError("Copied file checksum mismatch")
                    os.link(temp, dest)  # no overwrite
                finally:
                    temp.unlink(missing_ok=True)
                result["copied"] += 1
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    export = sub.add_parser("pack")
    export.add_argument("--root", required=True, type=Path)
    export.add_argument("--bundle", required=True, type=Path)
    check = sub.add_parser("verify")
    check.add_argument("--bundle", required=True, type=Path)
    imp = sub.add_parser("import")
    imp.add_argument("--bundle", required=True, type=Path)
    imp.add_argument("--destination", required=True, type=Path)
    imp.add_argument("--copy", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "pack":
            result = pack(args.root, args.bundle)
        elif args.action == "verify":
            _, result = verify(args.bundle)
        else:
            result = import_inputs(args.bundle, args.destination, copy=args.copy)
    except (OSError, ValueError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
