#!/usr/bin/env python3
import argparse, json, os, subprocess, concurrent.futures, hashlib, time
from pathlib import Path


def load_tasks(path):
    header = None; tasks = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            obj = json.loads(line)
            if obj['kind'] == 'header': header = obj
            elif obj['kind'] == 'task': tasks.append(obj)
    if header is None: raise SystemExit('missing header')
    return header, tasks


def run_one(exe, outdir, timeout, task):
    tid = task['task_id']
    outpath = Path(outdir) / f'{tid}.log'
    metapath = Path(outdir) / f'{tid}.meta.json'
    cmd = [exe, str(task['m']), task['fixed_prefix'], str(task['verbose']), str(task['enum_threshold'])]
    t0 = time.time()
    try:
        with outpath.open('wb') as out:
            proc = subprocess.run(cmd, stdout=out, stderr=subprocess.STDOUT, timeout=timeout)
        ec = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired:
        ec = 124; timed_out = True
        with outpath.open('ab') as out:
            out.write(b'\nTIMEOUT\n')
    data = outpath.read_bytes() if outpath.exists() else b''
    h = hashlib.sha256(data).hexdigest()
    meta = {'task_id': tid, 'cmd': cmd, 'exit_code': ec, 'timed_out': timed_out, 'seconds': time.time()-t0, 'log_sha256': h}
    metapath.write_text(json.dumps(meta, sort_keys=True, indent=2), encoding='utf-8')
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True)
    ap.add_argument('--tasks', default='tasks.jsonl')
    ap.add_argument('--out', default='runs')
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--timeout', type=int, default=3600)
    args = ap.parse_args()
    Path(args.out).mkdir(parents=True, exist_ok=True)
    header, tasks = load_tasks(args.tasks)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futs = [pool.submit(run_one, args.exe, args.out, args.timeout, t) for t in tasks]
        for fut in concurrent.futures.as_completed(futs):
            meta = fut.result()
            print(json.dumps(meta, sort_keys=True), flush=True)

if __name__ == '__main__':
    main()
