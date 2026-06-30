#!/usr/bin/env python3
import argparse, json, hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='tasks.jsonl')
    ap.add_argument('--mode', choices=['k1'], default='k1')
    ap.add_argument('--m', type=int, default=96)
    ap.add_argument('--k1-min', type=int, default=1)
    ap.add_argument('--k1-max', type=int, default=75)
    ap.add_argument('--verbose', type=int, default=0)
    ap.add_argument('--enum-threshold', type=int, default=256)
    ap.add_argument('--source', default='affine_ladder_prefix.cpp')
    args = ap.parse_args()

    source_hash = sha256_file(Path(args.source)) if Path(args.source).exists() else None
    with open(args.out, 'w', encoding='utf-8') as out:
        header = {
            'kind': 'header',
            'cover': f'm{args.m}_k1_{args.k1_min}_{args.k1_max}',
            'm': args.m,
            'k1_min': args.k1_min,
            'k1_max': args.k1_max,
            'source': args.source,
            'source_sha256': source_hash,
            'engine_args_schema': ['m', 'prefix_csv', 'verbose', 'enum_threshold']
        }
        out.write(json.dumps(header, sort_keys=True) + '\n')
        for k1 in range(args.k1_min, args.k1_max + 1):
            task = {
                'kind': 'task',
                'task_id': f'm{args.m}_k1_{k1:02d}',
                'm': args.m,
                'fixed_prefix': str(k1),
                'k1': k1,
                'verbose': args.verbose,
                'enum_threshold': args.enum_threshold,
                'expected': {'exit_code': 0, 'result': 'PASS', 'hits': 0}
            }
            out.write(json.dumps(task, sort_keys=True) + '\n')

if __name__ == '__main__':
    main()
