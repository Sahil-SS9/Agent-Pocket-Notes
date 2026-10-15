"""Private session registry and file outboxes; a single atomic claim wins delivery."""
from __future__ import annotations
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import re
import time
import uuid
from .io import FileLock, atomic_write, private_dir

log = logging.getLogger(__name__)


def safe_token(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,199}',value):
        raise ValueError('Invalid session or target id')
    return value


def pid_alive(pid):
    if isinstance(pid,bool) or not isinstance(pid,int) or pid <= 0:
        return False
    if os.name == 'nt':
        # os.kill(pid, 0) is not a safe Windows liveness probe.
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied means alive
        try:
            code = ctypes.c_ulong()
            return bool(kernel.GetExitCodeProcess(ctypes.c_void_p(handle),ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid,0)
        return True
    except PermissionError:
        return True
    except ProcessLookupError:
        return False


class Registry:
    def __init__(self,home):
        self.home = Path(home)
        self.directory = private_dir(self.home/'sessions')
        self.lock = self.home/'sessions.lock'

    def register(self,kind,session_id,*,pid=None,cwd=None,transcript_path=None,clock=None):
        safe_token(session_id)
        if kind not in {'hermes','claude'}:
            raise ValueError('Only classic Hermes CLI and Claude sessions are supported')
        if kind == 'hermes' and (not isinstance(pid,int) or isinstance(pid,bool) or pid<=0):
            raise ValueError('Hermes requires a positive pid')
        stamp = time.time() if clock is None else clock
        target = f'{kind}-{pid if kind=="hermes" else session_id}'
        path = self.directory/f'{target}.json'
        with FileLock(self.lock):
            previous = {}
            if path.exists():
                try:
                    previous = json.loads(path.read_text('utf-8'))
                except (ValueError,OSError):
                    pass
            record = dict(kind=kind,pid=pid,session_id=session_id,cwd=str(cwd or os.getcwd()),
                          started=previous.get('started',stamp),heartbeat=stamp,target=target)
            if transcript_path is not None:
                record['transcript_path'] = str(transcript_path)
            atomic_write(path,json.dumps(record).encode())
        return record

    def list(self,*,clock=None):
        stamp = time.time() if clock is None else clock
        results=[]
        with FileLock(self.lock):
            for path in self.directory.glob('*.json'):
                try:
                    if path.is_symlink():
                        continue
                    item=json.loads(path.read_text('utf-8'))
                    kind=item['kind']; safe_token(item['session_id']); safe_token(item['target'])
                    timeout={'hermes':60,'claude':12*60*60}[kind]
                    live=stamp-item['heartbeat']<=timeout and (kind!='hermes' or pid_alive(item['pid']))
                    if item['target']+'.json' != path.name:
                        live=False
                    if live:
                        results.append(item)
                    else:
                        path.unlink(missing_ok=True)
                except (OSError,ValueError,KeyError,TypeError):
                    path.unlink(missing_ok=True)
        return sorted(results,key=lambda item:item['started'],reverse=True)

    def remove(self,target):
        with FileLock(self.lock):
            (self.directory/f'{safe_token(target)}.json').unlink(missing_ok=True)


def context_message(note):
    body,separator,research=note.body.partition('\n\n## Research —')
    message=f'📌 Note #{note.id} from my sticky board (for context):\n{body}'
    if separator:
        message+='\n\nResearch so far:\n## Research —'+research
    return message


def enqueue(store,note_id,target):
    note=store.get(note_id)
    directory=private_dir(store.home/'outbox'/safe_token(target))
    path=directory/f'{uuid.uuid4().hex}.json'
    atomic_write(path,json.dumps({'note_id':note.id,'message':context_message(note),'queued':time.time()},ensure_ascii=False).encode())
    return path


@dataclass
class Claim:
    path: Path
    original: Path
    message: str

    def ack(self):
        self.path.unlink(missing_ok=True)

    def retry(self):
        os.replace(self.path,self.original)


def claim_messages(home,target):
    directory=Path(home)/'outbox'/safe_token(target)
    for path in sorted(directory.glob('*.json')):
        if path.is_symlink():
            continue
        claimed=path.with_suffix(f'.claim-{os.getpid()}-{uuid.uuid4().hex}')
        try:
            os.rename(path,claimed)
        except FileNotFoundError:  # another consumer won
            continue
        try:
            if claimed.stat().st_size > 2*1024*1024:
                raise ValueError('Oversize outbox item')
            item=json.loads(claimed.read_text('utf-8'))
            if not isinstance(item.get('message'),str):
                raise ValueError('Outbox message must be text')
            yield Claim(claimed,path,item['message'])
        except (ValueError,TypeError,OSError) as exc:
            log.warning('Invalid sticky outbox item %s: %s',claimed,exc)
            os.replace(claimed,claimed.with_suffix('.failed'))


def deliver_pending(home,target,inject):
    delivered=0
    for claim in claim_messages(home,target):
        try:
            accepted=inject(claim.message)
        except Exception:
            claim.retry()
            log.exception('Sticky delivery refused; note requeued')
            continue
        if accepted:
            claim.ack()
            delivered+=1
        else:
            claim.retry()
    return delivered


def send_note(store,note_id,kind,*,session=None):
    if kind=='clipboard':
        from .clipboard import write_clipboard
        note=store.get(note_id)
        write_clipboard(f'Context from my notes (#{note.id}):\n{note.body}')
        return f'Copied #{note.id} to clipboard'
    matches=[s for s in Registry(store.home).list() if s['kind']==kind and (session is None or session in (s['session_id'],s['target']))]
    if not matches:
        raise ValueError(f'No live {kind} session; use clipboard or start its adapter')
    if len(matches)!=1:
        raise ValueError('Choose a session with --session; more than one is live')
    target=matches[0]
    enqueue(store,note_id,target['target'])
    suffix=' (attached to your next message)' if kind=='claude' else ' (queued for the CLI plugin)'
    return f'Queued #{note_id} to {kind} · {target["cwd"]}{suffix}'
