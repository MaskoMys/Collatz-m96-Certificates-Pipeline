#!/usr/bin/env python3
import argparse
import errno
import fcntl
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from verify_certificate import verify_artifact_pair

TASK_ID_ALLOWED = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-')
PARTIAL_DIR = '.partial'
STATUS_DIR = '.status'
QUARANTINE_DIR = '.quarantine'
LOCK_FILE = '.runner.lock'

STOP_REQUESTED = False


def load_tasks(path):
    header = None
    tasks = []
    with open(path, encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            obj = json.loads(line)
            if obj['kind'] == 'header':
                header = obj
            elif obj['kind'] == 'task':
                tasks.append(obj)
            else:
                raise ValueError(f'{path}:{lineno}: bad kind')
    if header is None:
        raise SystemExit('missing header')
    if not tasks:
        raise SystemExit('missing tasks')
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


def task_paths(outdir, task_id):
    return (
        Path(outdir) / f'{task_id}.log',
        Path(outdir) / f'{task_id}.meta.json',
    )


def partial_paths(outdir, task_id):
    partial = Path(outdir) / PARTIAL_DIR
    return (
        partial / f'{task_id}.log',
        partial / f'{task_id}.meta.json',
    )


def status_path(outdir, task_id):
    return Path(outdir) / STATUS_DIR / f'{task_id}.json'


def command_for(exe, task):
    return [
        exe,
        str(task['m']),
        task['fixed_prefix'],
        str(task['verbose']),
        str(task['enum_threshold']),
    ]


def order_tasks(tasks, order):
    if order == 'manifest':
        return list(tasks)
    reverse = order == 'desc'
    return sorted(tasks, key=lambda task: task['k1'], reverse=reverse)


def sha256_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, obj):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(obj, sort_keys=True, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def emit(obj):
    print(json.dumps(obj, sort_keys=True), flush=True)


def format_seconds(seconds):
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f'{days}d{hours:02d}h'
    if hours:
        return f'{hours}h{minutes:02d}m'
    if minutes:
        return f'{minutes}m{secs:02d}s'
    return f'{secs}s'


def format_bytes(size):
    size = int(size or 0)
    units = ('B', 'KiB', 'MiB', 'GiB')
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == 'B':
                return f'{size}B'
            return f'{value:.1f}{unit}'
        value /= 1024


def progress_bar(done, total, width=30):
    if total <= 0:
        return '[' + '.' * width + ']'
    filled = min(width, int(width * done / total))
    return '[' + '#' * filled + '.' * (width - filled) + ']'


def active_tasks(summary):
    return summary.get('active') or summary.get('running_tasks') or []


def human_progress_lines(summary):
    total = summary.get('total', 0)
    completed = summary.get('completed', 0)
    running = summary.get('running', 0)
    pending = summary.get('pending', 0)
    quarantined = summary.get('quarantined', summary.get('failed', 0))
    invalid = summary.get('invalid', 0)
    stale = summary.get('stale_status', 0)
    skipped = summary.get('skipped', 0)
    elapsed = summary.get('elapsed_seconds')
    pct = (100.0 * completed / total) if total else 0.0
    parts = [
        f'{progress_bar(completed, total)} {completed}/{total} complete ({pct:.1f}%)',
        f'running {running}',
        f'pending {pending}',
        f'quarantined {quarantined}',
    ]
    if skipped:
        parts.append(f'skipped {skipped}')
    if invalid:
        parts.append(f'invalid {invalid}')
    if stale:
        parts.append(f'stale {stale}')
    if elapsed is not None:
        parts.append(f'elapsed {format_seconds(elapsed)}')
    lines = [' | '.join(parts)]

    active = sorted(active_tasks(summary), key=lambda x: (x.get('k1') is None, x.get('k1') or 0, x.get('task_id') or ''))
    if active:
        lines.append('active:')
        for item in active:
            task_id = item.get('task_id', '?')
            k1 = item.get('k1', '?')
            pid = item.get('pid', '?')
            elapsed_task = format_seconds(item.get('elapsed_seconds', 0))
            log_bytes = format_bytes(item.get('log_bytes', 0))
            lines.append(f'  {task_id} k1={k1} pid={pid} elapsed={elapsed_task} log={log_bytes}')

    pending_tasks = summary.get('pending_tasks') or []
    if pending_tasks:
        suffix = ' ...' if summary.get('pending', 0) > len(pending_tasks) else ''
        lines.append('next: ' + ', '.join(pending_tasks) + suffix)

    invalid_tasks = summary.get('invalid_tasks') or []
    if invalid_tasks:
        rendered = ', '.join(x.get('task_id', '?') for x in invalid_tasks[:5])
        suffix = ' ...' if len(invalid_tasks) > 5 else ''
        lines.append('invalid: ' + rendered + suffix)

    return lines


def print_human_progress(summary, stream=sys.stderr):
    print('\n'.join(human_progress_lines(summary)), file=stream, flush=True)


def pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as e:
        return e.errno == errno.EPERM
    return True


def quarantine_attempt_dir(outdir, task_id, reason):
    stamp = time.strftime('%Y%m%d_%H%M%S')
    base = Path(outdir) / QUARANTINE_DIR / f'{stamp}_{task_id}_{reason}'
    path = base
    i = 1
    while path.exists():
        path = Path(f'{base}_{i}')
        i += 1
    path.mkdir(parents=True, exist_ok=False)
    return path


def quarantine_paths(outdir, task_id, reason, paths, detail=None):
    paths = [Path(p) for p in paths if p and Path(p).exists()]
    if not paths and detail is None:
        return None
    dest = quarantine_attempt_dir(outdir, task_id, reason)
    for p in paths:
        os.replace(p, dest / p.name)
    if detail is not None:
        write_json(dest / 'failure.json', detail)
    return dest


def ensure_layout(outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / PARTIAL_DIR).mkdir(exist_ok=True)
    (out / STATUS_DIR).mkdir(exist_ok=True)
    (out / QUARANTINE_DIR).mkdir(exist_ok=True)


def acquire_lock(outdir):
    lock_path = Path(outdir) / LOCK_FILE
    fh = lock_path.open('a+', encoding='utf-8')
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(f'another runner already holds {lock_path}')
    fh.seek(0)
    fh.truncate()
    fh.write(json.dumps({'pid': os.getpid(), 'started_at': time.time()}, sort_keys=True) + '\n')
    fh.flush()
    return fh


def cleanup_stale_work(outdir):
    out = Path(outdir)
    for subdir, reason in ((PARTIAL_DIR, 'stale_partial'), (STATUS_DIR, 'stale_status')):
        d = out / subdir
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.is_file():
                task_id = p.stem
                if task_id.endswith('.meta'):
                    task_id = task_id[:-5]
                if task_id.endswith('.tmp'):
                    task_id = task_id[:-4]
                if not task_id:
                    task_id = 'unknown'
                quarantine_paths(outdir, task_id, reason, [p])


def verify_existing(task, outdir, exe):
    tid = task['task_id']
    log, meta = task_paths(outdir, tid)
    try:
        return verify_artifact_pair(task, log, meta, exe), None
    except Exception as e:
        return None, str(e)


def existing_root_state(task, outdir, exe):
    tid = task['task_id']
    log, meta = task_paths(outdir, tid)
    if not log.exists() and not meta.exists():
        return 'missing', None, None
    if log.exists() and meta.exists():
        ok, err = verify_existing(task, outdir, exe)
        if ok is not None:
            return 'valid', ok, None
        return 'invalid', None, err
    return 'invalid', None, f'incomplete root artifacts for {tid}'


def count_quarantined(outdir):
    quarantined = Path(outdir) / QUARANTINE_DIR
    if not quarantined.is_dir():
        return 0
    return sum(1 for p in quarantined.iterdir())


def read_status_records(outdir):
    status_dir = Path(outdir) / STATUS_DIR
    records = []
    if not status_dir.is_dir():
        return records
    for path in sorted(status_dir.glob('*.json')):
        try:
            obj = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            obj = {'task_id': path.stem, 'status_error': 'unreadable'}
        obj['_path'] = str(path)
        records.append(obj)
    return records


def summarize(outdir, tasks, exe=None):
    completed = []
    invalid = []
    missing = []
    for task in tasks:
        state, ok, err = existing_root_state(task, outdir, exe)
        if state == 'valid':
            completed.append(ok['task_id'])
        elif state == 'invalid':
            invalid.append({'task_id': task['task_id'], 'error': err})
        else:
            missing.append(task['task_id'])

    running = []
    stale = []
    for rec in read_status_records(outdir):
        pid = rec.get('pid')
        item = {
            'task_id': rec.get('task_id'),
            'k1': rec.get('k1'),
            'pid': pid,
            'elapsed_seconds': max(0.0, time.time() - rec.get('start_time', time.time())),
            'log_bytes': rec.get('log_bytes', 0),
        }
        if pid_alive(pid):
            running.append(item)
        else:
            stale.append(item)

    running_ids = {x['task_id'] for x in running}
    pending = [
        tid for tid in missing
        if tid not in running_ids
    ] + [x['task_id'] for x in invalid]

    return {
        'event': 'status',
        'total': len(tasks),
        'completed': len(completed),
        'running': len(running),
        'pending': len(pending),
        'quarantined': count_quarantined(outdir),
        'invalid': len(invalid),
        'stale_status': len(stale),
        'running_tasks': running,
        'pending_tasks': pending[:10],
        'invalid_tasks': invalid[:10],
    }


def heartbeat(outdir, tasks, completed_count, skipped_count, pending, running, quarantined_count, start_time):
    active = []
    now = time.time()
    for item in running.values():
        log_bytes = item['partial_log'].stat().st_size if item['partial_log'].exists() else 0
        active.append({
            'task_id': item['task']['task_id'],
            'k1': item['task'].get('k1'),
            'pid': item['proc'].pid,
            'elapsed_seconds': now - item['start_time'],
            'log_bytes': log_bytes,
        })
        status = item['status']
        status['elapsed_seconds'] = now - item['start_time']
        status['log_bytes'] = log_bytes
        write_json(item['status_path'], status)
    return {
        'event': 'heartbeat',
        'elapsed_seconds': now - start_time,
        'total': len(tasks),
        'completed': completed_count,
        'skipped': skipped_count,
        'running': len(running),
        'pending': len(pending),
        'quarantined': quarantined_count + count_quarantined(outdir),
        'active': active,
        'pending_tasks': [task['task_id'] for task in pending[:10]],
    }


def launch_task(exe, outdir, task):
    tid = task['task_id']
    validate_task_id(tid)
    partial_log, partial_meta = partial_paths(outdir, tid)
    partial_log.parent.mkdir(exist_ok=True)
    partial_meta.parent.mkdir(exist_ok=True)
    for p in (partial_log, partial_meta, status_path(outdir, tid)):
        if p.exists():
            quarantine_paths(outdir, tid, 'stale_before_launch', [p])
    cmd = command_for(exe, task)
    start = time.time()
    log_handle = partial_log.open('wb')
    try:
        proc = subprocess.Popen(cmd, stdout=log_handle, stderr=subprocess.STDOUT)
    except OSError as e:
        log_handle.write(f'EXEC_ERROR: {e}\n'.encode())
        log_handle.close()
        raise
    status = {
        'task_id': tid,
        'k1': task.get('k1'),
        'pid': proc.pid,
        'cmd': cmd,
        'start_time': start,
        'started_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(start)),
        'log_bytes': 0,
    }
    spath = status_path(outdir, tid)
    write_json(spath, status)
    return {
        'task': task,
        'cmd': cmd,
        'proc': proc,
        'log_handle': log_handle,
        'partial_log': partial_log,
        'partial_meta': partial_meta,
        'status_path': spath,
        'status': status,
        'start_time': start,
        'timed_out': False,
    }


def terminate_item(item):
    proc = item['proc']
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def finish_item(item, outdir, exe, timed_out=False):
    task = item['task']
    tid = task['task_id']
    proc = item['proc']
    if timed_out and proc.poll() is None:
        terminate_item(item)
    ec = 124 if timed_out else proc.poll()
    item['log_handle'].close()
    if timed_out:
        with item['partial_log'].open('ab') as out:
            out.write(b'\nTIMEOUT\n')
    seconds = time.time() - item['start_time']
    h = sha256_file(item['partial_log']) if item['partial_log'].exists() else hashlib.sha256(b'').hexdigest()
    meta = {
        'task_id': tid,
        'cmd': item['cmd'],
        'exit_code': ec,
        'timed_out': timed_out,
        'seconds': seconds,
        'log_sha256': h,
    }
    write_json(item['partial_meta'], meta)

    try:
        verify_artifact_pair(task, item['partial_log'], item['partial_meta'], exe)
    except Exception as e:
        detail = dict(meta)
        detail['error'] = str(e)
        dest = quarantine_paths(
            outdir,
            tid,
            'rejected_attempt',
            [item['partial_log'], item['partial_meta'], item['status_path']],
            detail,
        )
        event = dict(meta)
        event.update({'event': 'quarantined', 'error': str(e), 'quarantine_dir': str(dest)})
        emit(event)
        return False, meta

    final_log, final_meta = task_paths(outdir, tid)
    os.replace(item['partial_log'], final_log)
    os.replace(item['partial_meta'], final_meta)
    if item['status_path'].exists():
        item['status_path'].unlink()
    emit(meta)
    return True, meta


def handle_signal(signum, _frame):
    global STOP_REQUESTED
    STOP_REQUESTED = True
    emit({'event': 'signal', 'signal': signum, 'message': 'stopping after cleaning up active tasks'})


def prepare_tasks(tasks, outdir, exe, resume, retry_invalid):
    runnable = []
    skipped = 0
    completed = 0
    for task in tasks:
        tid = task['task_id']
        validate_task_id(tid)
        state, ok, err = existing_root_state(task, outdir, exe)
        if state == 'valid':
            completed += 1
            if resume:
                skipped += 1
                continue
        elif state == 'invalid':
            if not retry_invalid:
                raise SystemExit(f'{tid}: invalid existing artifacts; use --retry-invalid to quarantine and rerun ({err})')
            log, meta = task_paths(outdir, tid)
            quarantine_paths(outdir, tid, 'invalid_root', [log, meta], {'task_id': tid, 'error': err})
        runnable.append(task)
    return runnable, completed, skipped


def run_tasks(args, tasks):
    ensure_layout(args.out)
    lock_fh = acquire_lock(args.out)
    cleanup_stale_work(args.out)

    pending, existing_completed, skipped = prepare_tasks(
        tasks,
        args.out,
        args.exe,
        args.resume,
        args.retry_invalid,
    )
    completed = existing_completed if args.resume else 0
    quarantined = 0
    running = {}
    start_time = time.time()
    next_heartbeat = start_time + args.heartbeat_seconds if args.heartbeat_seconds else None
    timeout = None if args.timeout == 0 else args.timeout

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    if args.progress:
        print_human_progress(heartbeat(args.out, tasks, completed, skipped, pending, running, quarantined, start_time))

    try:
        while pending or running:
            while pending and len(running) < args.jobs and not STOP_REQUESTED:
                task = pending.pop(0)
                item = launch_task(args.exe, args.out, task)
                running[task['task_id']] = item

            now = time.time()
            changed = False
            for tid, item in list(running.items()):
                timed_out = False
                if timeout is not None and item['proc'].poll() is None and now - item['start_time'] > timeout:
                    timed_out = True
                if item['proc'].poll() is not None or timed_out:
                    ok, _meta = finish_item(item, args.out, args.exe, timed_out)
                    running.pop(tid, None)
                    if ok:
                        completed += 1
                    else:
                        quarantined += 1
                    changed = True

            if args.progress and changed:
                print_human_progress(heartbeat(args.out, tasks, completed, skipped, pending, running, quarantined, start_time))

            if next_heartbeat is not None and time.time() >= next_heartbeat:
                payload = heartbeat(args.out, tasks, completed, skipped, pending, running, quarantined, start_time)
                emit(payload)
                if args.progress:
                    print_human_progress(payload)
                next_heartbeat = time.time() + args.heartbeat_seconds

            if STOP_REQUESTED:
                break
            if running:
                time.sleep(0.5)

    finally:
        if running:
            for tid, item in list(running.items()):
                terminate_item(item)
                item['log_handle'].close()
                detail = {
                    'task_id': tid,
                    'cmd': item['cmd'],
                    'exit_code': item['proc'].poll(),
                    'timed_out': False,
                    'seconds': time.time() - item['start_time'],
                    'error': 'runner interrupted',
                }
                quarantine_paths(
                    args.out,
                    tid,
                    'interrupted',
                    [item['partial_log'], item['partial_meta'], item['status_path']],
                    detail,
                )
            running.clear()

    if STOP_REQUESTED:
        raise SystemExit(130)
    if quarantined:
        raise SystemExit(1)
    lock_fh.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe')
    ap.add_argument('--tasks', default='manifests/tasks.jsonl')
    ap.add_argument('--out', default='dist/runs')
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--timeout', type=int, default=3600)
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--retry-invalid', action='store_true')
    ap.add_argument('--heartbeat-seconds', type=float, default=0)
    ap.add_argument('--progress', action='store_true', help='print human progress snapshots to stderr during runs')
    ap.add_argument('--order', choices=('manifest', 'asc', 'desc'), default='manifest')
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--human', action='store_true', help='print --status as a human progress summary')
    args = ap.parse_args()

    if args.jobs < 1:
        raise SystemExit('--jobs must be positive')
    if args.timeout < 0:
        raise SystemExit('--timeout must be non-negative')
    if args.heartbeat_seconds < 0:
        raise SystemExit('--heartbeat-seconds must be non-negative')
    if not args.status and not args.exe:
        raise SystemExit('--exe is required unless --status is used')

    _header, tasks = load_tasks(args.tasks)
    tasks = order_tasks(tasks, args.order)
    if args.status:
        payload = summarize(args.out, tasks, args.exe)
        if args.human:
            print_human_progress(payload, stream=sys.stdout)
        else:
            emit(payload)
        return

    validate_executable(args.exe)
    run_tasks(args, tasks)


if __name__ == '__main__':
    main()
