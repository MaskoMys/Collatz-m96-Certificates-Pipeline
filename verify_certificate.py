#!/usr/bin/env python3
import argparse, json, re, hashlib, sys
from pathlib import Path

RESULT_RE = re.compile(r'^RESULT:\s*(PASS|FAIL)\s*$', re.M)
HITS_RE = re.compile(r'\bHITS=(\d+)\b')
CASE_RE = re.compile(r'\bCASE=(\d+)\b')
RANGE_RE = re.compile(r'\bK1_RANGE=(\d+)\.\.(\d+)\b')


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1<<20), b''):
            h.update(chunk)
    return h.hexdigest()


def load(path):
    header=None; tasks=[]
    with open(path, encoding='utf-8') as f:
        for lineno,line in enumerate(f,1):
            if not line.strip(): continue
            obj=json.loads(line)
            if obj.get('kind')=='header': header=obj
            elif obj.get('kind')=='task': tasks.append(obj)
            else: raise ValueError(f'{path}:{lineno}: bad kind')
    if header is None: raise ValueError('missing header')
    return header,tasks


def audit_cover(header,tasks):
    kmin=header['k1_min']; kmax=header['k1_max']; m=header['m']
    seen=[]
    ids=set()
    for t in tasks:
        assert t['m']==m
        assert t['task_id'] not in ids
        ids.add(t['task_id'])
        assert t['fixed_prefix']==str(t['k1'])
        seen.append(t['k1'])
    expect=list(range(kmin,kmax+1))
    if sorted(seen)!=expect:
        missing=sorted(set(expect)-set(seen)); extra=sorted(set(seen)-set(expect))
        raise AssertionError(f'cover mismatch missing={missing} extra={extra}')


def verify_one(task,runs):
    tid=task['task_id']
    log=Path(runs)/f'{tid}.log'
    meta=Path(runs)/f'{tid}.meta.json'
    if not log.exists(): raise AssertionError(f'missing log {log}')
    if not meta.exists(): raise AssertionError(f'missing meta {meta}')
    m=json.loads(meta.read_text(encoding='utf-8'))
    if m['exit_code'] != task['expected']['exit_code']: raise AssertionError(f'{tid}: bad exit {m["exit_code"]}')
    if m.get('timed_out'): raise AssertionError(f'{tid}: timed out')
    data=log.read_text(encoding='utf-8', errors='replace')
    if sha256_file(log)!=m['log_sha256']: raise AssertionError(f'{tid}: bad log hash')
    res=RESULT_RE.findall(data)
    if res != [task['expected']['result']]: raise AssertionError(f'{tid}: bad RESULT markers {res}')
    hits=[int(x) for x in HITS_RE.findall(data)]
    if not hits: raise AssertionError(f'{tid}: HITS missing')
    if hits[-1] != task['expected']['hits']: raise AssertionError(f'{tid}: HITS={hits[-1]}')
    case=CASE_RE.findall(data)
    if not case or int(case[-1]) != task['m']: raise AssertionError(f'{tid}: CASE mismatch')
    rng=RANGE_RE.findall(data)
    if not rng: raise AssertionError(f'{tid}: K1_RANGE missing')
    lo,hi=map(int,rng[-1])
    if lo != task['k1'] or hi != task['k1']: raise AssertionError(f'{tid}: K1_RANGE {lo}..{hi} expected {task["k1"]}')
    return {'task_id':tid,'log_sha256':m['log_sha256']}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--tasks',default='tasks.jsonl')
    ap.add_argument('--runs',default='runs')
    ap.add_argument('--source',default='affine_ladder_prefix.cpp')
    args=ap.parse_args()
    header,tasks=load(args.tasks)
    audit_cover(header,tasks)
    if Path(args.source).exists() and header.get('source_sha256'):
        actual=sha256_file(Path(args.source))
        if actual != header['source_sha256']:
            raise AssertionError(f'source hash mismatch {actual} != {header["source_sha256"]}')
    cert=[]
    for t in tasks:
        cert.append(verify_one(t,args.runs))
    payload=''.join(x['log_sha256'] for x in sorted(cert,key=lambda x:x['task_id'])).encode()
    combined=hashlib.sha256(payload).hexdigest()
    summary={'verified_tasks':len(tasks),'cover':header['cover'],'combined_log_hash':combined,'result':'ACCEPT'}
    print(json.dumps(summary,sort_keys=True,indent=2))

if __name__=='__main__':
    try:
        main()
    except Exception as e:
        print(f'REJECT: {e}', file=sys.stderr)
        sys.exit(1)
