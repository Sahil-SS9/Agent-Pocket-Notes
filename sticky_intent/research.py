"""Detached one-shot research supervisors. Configured argv, never a shell string."""
from __future__ import annotations
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tomllib
import uuid
import re
import shlex
from .io import FileLock, atomic_write, private_dir
from .store import Store, BODY_LIMIT, now, valid_id

PROMPT='Investigate the note below. Reply with: a 3-line summary, key facts with sources, open questions, suggested next steps.\n\n'
DEFAULTS={'hermes':['hermes','chat','-Q','-q','{prompt}'],'claude':['claude','-p','{prompt}']}


OPTION_DEFAULTS=dict(executable='hermes',profile='',provider='',model='',home='')


def hermes_options(store):
    path=store.home/'config.toml'
    config=tomllib.loads(path.read_text('utf-8')) if path.exists() else {}
    values={**OPTION_DEFAULTS,**config.get('research',{}).get('hermes_options',{})}
    for key,value in values.items():
        if key not in OPTION_DEFAULTS or not isinstance(value,str) or len(value)>4096 or any(c in value for c in '\n\r\x00'):
            raise ValueError('Invalid Hermes research option: '+key)
    if not values['executable']: raise ValueError('Hermes executable is required')
    if values['profile'] and not re.fullmatch(r'[\w.-]+',values['profile']): raise ValueError('Invalid Hermes profile name')
    if values['home'] and not Path(values['home']).expanduser().is_absolute(): raise ValueError('Hermes home must be an absolute path')
    return values


def save_hermes_options(store,options):
    path=store.home/'config.toml'
    with FileLock(store.lock_path):
        text=path.read_text('utf-8') if path.exists() else ''
        existing=hermes_options(store)
        existing.update(options)
        # Replace only our owned table; preserve custom argv and unrelated TOML verbatim.
        lines=text.splitlines(keepends=True); kept=[]; inside=False
        for line in lines:
            if re.fullmatch(r'\s*\[research\.hermes_options\]\s*(?:#.*)?\n?',line): inside=True; continue
            if inside and line.lstrip().startswith('['): inside=False
            if not inside: kept.append(line)
        result=''.join(kept)
        if result and not result.endswith('\n'): result+='\n'
        result+='[research.hermes_options]\n'+''.join(k+' = '+json.dumps(v,ensure_ascii=False)+'\n' for k,v in existing.items())
        parsed=tomllib.loads(result)['research']['hermes_options']
        if any(k not in OPTION_DEFAULTS or not isinstance(v,str) or any(c in v for c in '\n\r\x00') or len(v)>4096 for k,v in parsed.items()):
            raise ValueError('Invalid Hermes research options')
        if not parsed['executable']: raise ValueError('Hermes executable is required')
        if parsed['profile'] and not re.fullmatch(r'[\w.-]+',parsed['profile']): raise ValueError('Invalid Hermes profile name')
        if parsed['home'] and not Path(parsed['home']).expanduser().is_absolute(): raise ValueError('Hermes home must be an absolute path')
        atomic_write(path,result.encode())


def hermes_setup_command(store):
    options=hermes_options(store)
    args=[options['executable']]
    if options['profile']: args+=['--profile',options['profile']]
    args+=['model']
    prefix=('HERMES_HOME='+shlex.quote(str(Path(options['home']).expanduser()))+' ') if options['home'] else ''
    return prefix+shlex.join(args)


def research_config(store,runner,timeout=None):
    if runner not in DEFAULTS:
        raise ValueError('Research runner must be hermes or claude')
    path=store.home/'config.toml'
    config=tomllib.loads(path.read_text('utf-8')).get('research',{}) if path.exists() else {}
    default=DEFAULTS[runner]
    if runner=='hermes':
        options=hermes_options(store)
        default=[options['executable']]
        if options['profile']: default+=['--profile',options['profile']]
        default+=['chat','-Q']
        for name in ['provider','model']:
            if options[name]: default+=['--'+name,options[name]]
        default+=['-q','{prompt}']
    argv=config.get(runner,default)
    if not isinstance(argv,list) or not argv or not all(isinstance(a,str) and a for a in argv):
        raise ValueError('Research command must be a non-empty TOML array of argv strings')
    seconds=float(timeout if timeout is not None else config.get('timeout_seconds',900))
    if not math.isfinite(seconds) or seconds<=0 or seconds>3600:
        raise ValueError('Research timeout must be positive and at most 3600 seconds')
    return argv,seconds


def start_research(store,note_id,runner='hermes',*,timeout=None):
    valid_id(note_id)
    argv,seconds=research_config(store,runner,timeout)
    directory=private_dir(store.home/'research')
    with FileLock(directory/f'note-{note_id}.lock'):
        note=store.get(note_id)
        if note.research=='running':
            raise ValueError('Research is already running for this note')
        job_id=uuid.uuid4().hex
        record={'job_id':job_id,'note_id':note.id,'runner':runner,'argv':[a.replace('{prompt}',PROMPT+note.body) for a in argv],
                'timeout':seconds,'log':str(directory/f'{job_id}.log'),'state':'queued'}
        if runner=='hermes':
            options=hermes_options(store)
            record['setup_command']=hermes_setup_command(store)
            if options['home']: record['hermes_home']=str(Path(options['home']).expanduser())
        job=directory/f'{job_id}.json'
        atomic_write(job,json.dumps(record).encode())
        store.update(note.id,research='running')
        try:
            process=subprocess.Popen([sys.executable,'-m','sticky_intent.research','--worker',str(job),'--home',str(store.home)],
                                     stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                     start_new_session=os.name!='nt',creationflags=(subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=='nt' else 0)
            # The supervisor publishes its own state, so parent/worker never overwrite
            # one another's job record. This pid sidecar is diagnostic only.
            atomic_write(directory/f'{job_id}.pid',str(process.pid).encode())
        except OSError:
            store.update(note.id,research='failed')
            raise
        return dict(pid=process.pid,runner=runner,log=record['log'],job_id=job_id)


def _terminate(process):
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
    else:
        try:
            os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=5)


def _append(store,note_id,runner,answer,success,log_path):
    with FileLock(store.lock_path):
        note=store.get(note_id)  # preserve edits/status made while the agent ran
        stamp=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        heading=f'\n\n## Research — {runner}, {stamp}\n'
        available=BODY_LIMIT-len((note.body+heading).encode())
        suffix=f'\n[Output truncated; full log: {log_path}]'
        if len(answer.encode())>available:
            room=available-len(suffix.encode())
            if room<=0:
                failed=replace(note,research='failed',updated=now())
                atomic_write(store._path(note.id),failed.encode())
                return False
            answer=answer.encode()[:room].decode('utf-8','ignore')+suffix
        result=replace(note,body=note.body+heading+answer,research='done' if success else 'failed',updated=now())
        atomic_write(store._path(note.id),result.encode())
        return success


def _notify(note_id,success,*,runner=None,operation='research'):
    if os.getenv('STICKY_INTENT_NO_NOTIFICATIONS') or os.getenv('STICKY_TESTING'):
        return
    exe=shutil.which('notify-send')
    if exe:
        try:
            caption=f'Note #{note_id}: '+operation+(' reply ready' if success else ' failed')+((' · '+runner) if runner else '')
            subprocess.run([exe,'Pocket Notes',caption],
                           stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=2)
        except (OSError,subprocess.TimeoutExpired):
            pass


def run_worker(job_path,home):
    store=Store(home)
    job_path=Path(job_path)
    record=json.loads(job_path.read_bytes())
    log_path=Path(record['log'])
    record.update(state='running',pid=os.getpid())
    atomic_write(job_path,json.dumps(record).encode())
    success=False; failure=''
    try:
        with log_path.open('xb') as log:
            if os.name!='nt':
                os.chmod(log_path,0o600)
            env=os.environ.copy()
            if record.get('hermes_home'): env['HERMES_HOME']=record['hermes_home']
            process=subprocess.Popen(record['argv'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                                     start_new_session=os.name!='nt',creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0)
            try:
                code=process.wait(timeout=record['timeout'])
                success=code==0
                if not success:
                    failure=f'Research failed: runner exited with code {code}.'
            except subprocess.TimeoutExpired:
                _terminate(process)
                failure=f'Research timed out after {record["timeout"]} seconds.'
        with log_path.open('rb') as log:
            answer=log.read(BODY_LIMIT+1).decode('utf-8','replace').strip()
        if not answer:
            success=False; failure=failure or 'Research failed: runner returned no answer.'
        if not success:
            if record['runner']=='hermes' and any(marker in answer.lower() for marker in ['no access token found','re-authenticate','authentication failed','not logged in']):
                record['failure_kind']='authentication'
                recovery=record.get('setup_command','hermes model')
                failure='Hermes authentication is required in the same desktop account that runs Pocket Notes. Open a terminal as that user and run: '+recovery+'. Then retry Research. No credentials were changed or copied.'
            answer=failure+'\n\n'+answer
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        failure=f'Research failed: {exc}'
        answer=failure
        if not log_path.exists():
            atomic_write(log_path,(failure+'\n').encode())
    try:
        success=_append(store,record['note_id'],record['runner'],answer,success,log_path)
    except (OSError,ValueError) as exc:
        success=False
        failure=f'Could not append research (note may have been trashed): {exc}'
        with log_path.open('ab') as log:
            log.write(('\n'+failure).encode())
    record.update(state='done' if success else 'failed',finished=now(),error=failure)
    atomic_write(job_path,json.dumps(record).encode())
    _notify(record['note_id'],success)
    return 0 if success else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',required=True)
    parser.add_argument('--home',required=True)
    args=parser.parse_args()
    raise SystemExit(run_worker(args.worker,args.home))
