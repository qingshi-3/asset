"""Verify the PNG package using its file and source indexes."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--sample', type=int, help='Hash at most this many evenly spaced images; default: all')
    args = parser.parse_args()
    root = args.root.resolve()
    summary = json.loads((root/'index/summary.json').read_text(encoding='utf-8'))
    rows = [json.loads(line) for line in (root/'index/files.jsonl').read_text(encoding='utf-8').splitlines()]
    paths = set()
    hashes = set()
    byte_count = 0
    hashed = 0
    stride = max(1, len(rows)//max(1, args.sample)) if args.sample is not None else 1
    for i, row in enumerate(rows):
        rel = PurePosixPath(row['path'])
        if rel.is_absolute() or '..' in rel.parts or not row['path'].startswith('assets/') or rel.suffix.lower() != '.png':
            raise ValueError('Invalid asset path: '+str(rel))
        path = root/row['path']
        if row['path'] in paths or path.stat().st_size != row['bytes']:
            raise ValueError('Duplicate path or byte mismatch: '+str(rel))
        paths.add(row['path'])
        hashes.add(row['sha256'])
        byte_count += row['bytes']
        if args.sample is None or (i%stride == 0 and hashed < args.sample):
            if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
                raise ValueError('Hash mismatch: '+str(rel))
            hashed += 1
    actual_paths = {p.relative_to(root).as_posix() for p in (root/'assets').rglob('*') if p.is_file()}
    if actual_paths != paths:
        raise ValueError('Disk assets differ from the file index')
    if len(rows) != summary['png_count'] or byte_count != summary['bytes'] or len(hashes) != summary['unique_sha256_count']:
        raise ValueError('Summary totals differ from the file index')
    mirror_count = 0
    for line in (root/'index/mirrors.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if row['sha256'] not in hashes:
            raise ValueError('Unresolved mirror: '+row['source'])
        mirror_count += 1
    if mirror_count != summary['mirror_count']:
        raise ValueError('Mirror count mismatch')
    print(json.dumps({'png_count':len(rows),'bytes':byte_count,'hashes_checked':hashed,'mirrors_matched':mirror_count}))


if __name__ == '__main__':
    main()
