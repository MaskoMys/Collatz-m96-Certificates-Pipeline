#!/usr/bin/env python3
import argparse, concurrent.futures, hashlib, json, os, shutil, subprocess, time
from pathlib import Path

TASK_ID_ALLOWED = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-')


def load_tasks(path):
    header = None; tasks = []
    with open(path, encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            obj = json.loads(line)
            if obj['kind'] == 'header': header = obj
            elif obj['kind'] == 'task': tasks.append(obj)
            else: raise ValueError(f'{path}:{lineno}: bad kind')
    if header is None: raise SystemExit('missing header')
    if not tasks: raise SystemExit('missing tasks')
    return header, tasks


def validate_task_id(task_id):
    if not task_id or any(ch not in TASK_ID_ALLOWED for ch in task_id):
        raise ValueError(f'unsafe task_id {task_id!r}')


def validate_executable(exe):
    path = Path(exe)
    if path.parent != Path('.'):
        if not path.is_file():
            raise SystemExit(f'executable does not exist: {exe}')
        if not os.access(path, os.X_OK):
            raise SystemExit(f'executable is not executable: {exe}')
        return
    if shutil.which(exe) is None:
        raise SystemExit(f'executable not found on PATH: {exe}')


def run_one(exe, outdir, timeout, task):
    tid = task['task_id']
    validate_task_id(tid)
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
    except OSError as e:
        ec = 127; timed_out = False
        with outpath.open('ab') as out:
            out.write(f'EXEC_ERROR: {e}\n'.encode())
    data = outpath.read_bytes() if outpath.exists() else b''
    h = hashlib.sha256(data).hexdigest()
    meta = {'task_id': tid, 'cmd': cmd, 'exit_code': ec, 'timed_out': timed_out, 'seconds': time.time()-t0, 'log_sha256': h}
    metapath.write_text(json.dumps(meta, sort_keys=True, indent=2), encoding='utf-8')
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True)
    ap.add_argument('--tasks', default='manifests/tasks.jsonl')
    ap.add_argument('--out', default='runs')
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--timeout', type=int, default=3600)
    args = ap.parse_args()
    if args.jobs < 1:
        raise SystemExit('--jobs must be positive')
    if args.timeout < 1:
        raise SystemExit('--timeout must be positive')
    validate_executable(args.exe)
    Path(args.out).mkdir(parents=True, exist_ok=True)
    header, tasks = load_tasks(args.tasks)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futs = [pool.submit(run_one, args.exe, args.out, args.timeout, t) for t in tasks]
        for fut in concurrent.futures.as_completed(futs):
            meta = fut.result()
            print(json.dumps(meta, sort_keys=True), flush=True)

if __name__ == '__main__':
    main()
