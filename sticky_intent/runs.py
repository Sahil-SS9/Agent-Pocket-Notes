"""Detached harness runs with success-only, idempotent note write-back."""
from __future__ import annotations
import argparse
from dataclasses import replace
from datetime import datetime,timezone
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from .harnesses import options_for,connection,build_command,parse_reply,environment,LABELS
from .io import FileLock,atomic_write,private_dir
from .store import Store,valid_id,BODY_LIMIT,now
from .research import _terminate,_notify

ACTIVE={'queued','running'}
OUTPUT_LIMIT=4*1024*1024


def jobs(store,note_id=None):
    rows=[]
    for path in (store.home/'runs').glob('*.json'):
        if path.is_symlink(): continue
        try:
            record=json.loads(path.read_bytes())
            if not isinstance(record,dict) or record.get('kind') not in LABELS or record.get('state') not in ACTIVE|{'done','failed','cancelled'}: continue
            if not isinstance(record.get('job_id'),str) or path.name!=record['job_id']+'.json' or not isinstance(record.get('created'),str): continue
            pid=record.get('pid')
            if not pid:
                try: pid=int(path.with_suffix('.pid').read_text())
                except (OSError,ValueError): pid=None
            if type(pid) is not int or pid<=0: pid=None
            if record['state'] in ACTIVE:
                from .targets import pid_alive
                try: age=(datetime.now(timezone.utc)-datetime.fromisoformat(record['created'].replace('Z','+00:00'))).total_seconds()
                except (ValueError,KeyError): age=0
                if age>5 and (not pid or not pid_alive(pid)):
                    record={**record,'state':'failed','interrupted':True,'error':'Run supervisor stopped before reporting completion. Inspect its log, then retry.'}
            if note_id is None or record.get('note_id')==note_id: rows.append(record)
        except (OSError,ValueError): continue
    return sorted(rows,key=lambda r:r.get('created',''),reverse=True)


def _scope(options):
    return tuple(options.get(k,'') for k in ['cwd','home','profile'])


def sessions(store,kind):
    current=options_for(store,kind); seen=set(); rows=[]
    busy={r.get('requested_session') for r in jobs(store) if r.get('kind')==kind and r.get('state') in ACTIVE}
    for job in jobs(store):
        session=job.get('session_id')
        if job.get('kind')!=kind or job.get('state')!='done' or not session or session in seen or _scope(job.get('options',{}))!=_scope(current): continue
        seen.add(session)
        rows.append(dict(session_id=session,label=LABELS[kind]+' · '+job.get('title','Note')+' · '+session,enabled=session not in busy))
    return rows


def _preview(body,limit=120):
    """The note's own text.

    Appended agent replies are written as a visible '## ✉ Reply — …' block followed by a
    '<!-- pocket-run: … -->' marker, so the preview cuts at the heading, not just the
    marker, otherwise the reply text shows up as if the user had written it.
    """
    text=body.split('<!-- pocket-run:')[0].split('## ✉ Reply')[0]
    lines=[line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    return ' '.join(lines)[:limit]


def note_history(store):
    """Notes that have agent activity, newest activity first, with harness/session metadata.

    The note itself stores no harness fields: every agent run is recorded under
    runs/<job_id>.json with its note_id, kind and session_id, so history is derived
    from those records and joined to the note for title, preview and status.
    """
    rows={}
    for job in jobs(store):
        note_id=job.get('note_id')
        if type(note_id) is not int or note_id<=0: continue
        row=rows.setdefault(note_id,dict(note_id=note_id,harnesses=[],session_id='',last_activity='',states=[]))
        kind=job.get('kind')
        if kind in LABELS and kind not in row['harnesses']: row['harnesses'].append(kind)
        session=job.get('session_id') or job.get('requested_session') or ''
        if session and not row['session_id']: row['session_id']=session
        if not row['last_activity']: row['last_activity']=job.get('created','')
        row['states'].append(job.get('state',''))
    live={}
    out=[]
    for note_id,row in rows.items():
        try: note=store.get(note_id)
        except (OSError,ValueError): continue
        kind=row['harnesses'][0] if row['harnesses'] else ''
        if kind and kind not in live:
            try: live[kind]={s['session_id'] for s in sessions(store,kind)}
            except (OSError,ValueError): live[kind]=set()
        out.append(dict(row,
                        is_header=False,
                        kind=kind,
                        label=LABELS[kind] if kind else 'Unknown harness',
                        harness_labels=[LABELS[k] for k in row['harnesses']],
                        title=note.title,
                        preview=_preview(note.body),
                        status=note.status,
                        updated=note.updated,
                        last_state=row['states'][0] if row['states'] else '',
                        replied='<!-- pocket-run:' in note.body,
                        resumable=bool(kind and row['session_id'] and row['session_id'] in live[kind])))
    return sorted(out,key=lambda r:r['last_activity'] or r['updated'],reverse=True)


def note_history_groups(store):
    """The same rows grouped by each harness the note was used with, biggest group first.

    A note used with two harnesses appears under both: the grouping answers "what did I
    use this harness for", so hiding it from either group would be a lie.
    """
    groups={}
    for row in note_history(store):
        for kind in (row['harnesses'] or ['']):
            groups.setdefault(kind,[]).append(row)
    out=[dict(kind=kind,label=LABELS[kind] if kind in LABELS else 'Unknown harness',count=len(items),notes=items)
         for kind,items in groups.items()]
    return sorted(out,key=lambda g:(-g['count'],g['label']))


def note_history_group_rows(store):
    """Flat header/note rows for the grouped view, so one delegate renders both."""
    rows=[]
    for group in note_history_groups(store):
        plural='note' if group['count']==1 else 'notes'
        rows.append(dict(is_header=True,key=group['kind'],
                         label=group['label']+' · '+str(group['count'])+' '+plural,
                         count=group['count']))
        rows.extend(group['notes'])
    return rows


def start_run(store,note_id,kind,operation='send',session=None,*,expected_updated=None):
    note_id=valid_id(note_id)
    if operation not in {'send','research'}: raise ValueError('Invalid run operation')
    snapshot=store.get(note_id)
    if not snapshot.body.strip(): raise ValueError('Write something in the note before starting agent work')
    if expected_updated is not None and snapshot.updated!=expected_updated: raise ValueError('Note changed before dispatch; save and retry')
    options=options_for(store,kind)
    if session and not any(s['session_id']==session and s['enabled'] for s in sessions(store,kind)):
        raise ValueError('Existing session is unknown, busy or belongs to a different workspace/profile')
    status=connection(kind,options,probe=True)
    if not status['can_run']: raise ValueError(status['reason'])
    options['executable']=status['executable']
    # Keep the saved executable spelling for session scope comparison (scope excludes it).
    directory=private_dir(store.home/'runs')
    with FileLock(directory/'runs.lock'):
        note=store.get(note_id)
        if note.updated!=snapshot.updated: raise ValueError('Note changed during connection checks; save and retry')
        existing=jobs(store)
        interrupted=[r for r in existing if r.get('note_id')==note_id and r.get('interrupted')]
        if interrupted and not any(r.get('note_id')==note_id and r.get('state') in ACTIVE for r in existing):
            for old in interrupted:
                receipt=directory/(old['job_id']+'.json')
                if receipt.exists(): atomic_write(receipt,json.dumps(old).encode())

            if note.research=='running': note=store.update(note_id,research='failed')
        if note.research=='running' or any(r.get('state') in ACTIVE and (r.get('note_id')==note_id or (session and r.get('kind')==kind and r.get('requested_session')==session)) for r in existing):
            raise ValueError('Agent work is already running for this note or session')
        job_id=uuid.uuid4().hex
        prompt=('Investigate this note. Return a concise answer, sources you actually checked, open questions and next steps.' if operation=='research' else 'Respond to the request in this note. Return the result to the user; do not overwrite the note, create tasks, or start background work.')+'\n\n'+note.body
        cwd=Path(options['cwd']).expanduser() if options['cwd'] else private_dir(store.home/'workspaces'/kind)
        if not cwd.is_dir(): raise ValueError('Selected working directory does not exist')
        argv=build_command(kind,prompt,options,session)
        input_file=directory/(job_id+'.prompt')
        if kind=='hermes':
            position=argv.index('-q'); argv[position:position+2]=['--query-file',str(input_file)]
        else:
            argv.remove(prompt)
            if kind=='codex': argv+=['-']
        atomic_write(input_file,prompt.encode())
        record=dict(job_id=job_id,note_id=note_id,kind=kind,operation=operation,requested_session=session or '',session_id='',title=note.title,options=options,cwd=str(cwd),argv=argv,input_file=str(input_file),prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),created=now(),state='queued',error='',log=str(directory/(job_id+'.log')),record=str(directory/(job_id+'.json')))
        atomic_write(Path(record['record']),json.dumps(record,ensure_ascii=False).encode())
        if operation=='research': store.update(note_id,research='running')
        try:
            process=subprocess.Popen([sys.executable,'-m','sticky_intent.runs','--worker',record['record'],'--home',str(store.home)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=os.name!='nt',env=environment(kind,options))
            atomic_write(directory/(job_id+'.pid'),str(process.pid).encode())
        except OSError as exc:
            record.update(state='failed',error=str(exc)); atomic_write(Path(record['record']),json.dumps(record).encode())
            if operation=='research': store.update(note_id,research='failed')
            raise
        return record


def append_reply(store,record,reply):
    marker='<!-- pocket-run: '+record['job_id']+' -->'
    with FileLock(store.lock_path):
        note=store.get(record['note_id'])
        if marker in note.body: return False
        stamp=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        text='\n\n## ✉ Reply — '+LABELS[record['kind']]+', '+stamp+'\n❝\n'+reply['text']+'\n❞ — '+LABELS[record['kind']]+'\nSession: '+(reply['session_id'] or 'not supplied by harness')+'\n'+marker
        if len((note.body+text).encode())>BODY_LIMIT:
            raise ValueError('Reply exceeds the note limit. Original note preserved; full output remains in the run log.')
        updated=replace(note,body=note.body+text,updated=now(),research='done' if record['operation']=='research' else note.research)
        atomic_write(store._path(note.id),updated.encode())
    return True


def worker(path,home):
    store=Store(home); path=Path(path)
    record=json.loads(path.read_bytes())
    if record.get('state')=='done': return 0
    record.update(state='running',pid=os.getpid(),started=now()); atomic_write(path,json.dumps(record).encode())
    log=Path(record['log']); stdout=log.with_suffix('.stdout'); stderr=log.with_suffix('.stderr')
    reply=dict(success=False,text='',session_id='',error='Harness did not finish')
    failure=''
    try:
        with stdout.open('xb') as out,stderr.open('xb') as err,Path(record['input_file']).open('rb') as incoming:
            os.chmod(stdout,0o600); os.chmod(stderr,0o600)
            if hashlib.file_digest(incoming,'sha256').hexdigest()!=record['prompt_sha256']: raise ValueError('Run input changed before dispatch; original note preserved')
            incoming.seek(0)
            process=subprocess.Popen(record['argv'],cwd=record['cwd'],env=environment(record['kind'],record['options']),stdin=incoming,stdout=out,stderr=err,start_new_session=os.name!='nt')
            deadline=time.monotonic()+900
            while process.poll() is None:
                if time.monotonic()>deadline or stdout.stat().st_size+stderr.stat().st_size>OUTPUT_LIMIT:
                    failure='Agent run timed out or exceeded its output limit'; _terminate(process); break
                time.sleep(.05)
            code=process.wait()
        raw=stdout.read_bytes()[:OUTPUT_LIMIT].decode('utf-8','replace')
        diagnostic=stderr.read_bytes()[:OUTPUT_LIMIT].decode('utf-8','replace')
        atomic_write(log,('STDERR\n'+diagnostic+'\nSTRUCTURED STDOUT\n'+raw).encode())
        reply=parse_reply(record['kind'],raw,code)
        if failure: reply.update(success=False,text='',error=failure)
        if reply['success']:
            if not reply['session_id'] and record.get('requested_session'): reply['session_id']=record['requested_session']
            append_reply(store,record,reply)
        else:
            failure=reply['error']
            if any(x in (raw+'\n'+diagnostic).lower() for x in ['no access token','auth_required','not logged in','authentication','re-authenticate']):
                failure='Authentication required for '+LABELS[record['kind']]+'. Use Connect / configure in the same desktop account, then check connection and retry.'
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        reply.update(success=False,text=''); failure=str(exc)
        if not log.exists(): atomic_write(log,(failure+'\n').encode())
    if not reply['success'] and record['operation']=='research':
        try: store.update(record['note_id'],research='failed')
        except (OSError,ValueError): pass
    record.update(state='done' if reply['success'] else 'failed',error=failure,session_id=reply['session_id'],finished=now())
    atomic_write(path,json.dumps(record,ensure_ascii=False).encode())
    _notify(record['note_id'],reply['success'],runner=LABELS[record['kind']],operation=record['operation'])
    return 0 if reply['success'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--worker',required=True); parser.add_argument('--home',required=True)
    args=parser.parse_args(); raise SystemExit(worker(args.worker,args.home))
