"""Claude's documented hook JSON protocol, reversible settings and /sticky command."""
from __future__ import annotations
import base64
import hashlib
import json
import logging
from pathlib import Path
from .io import FileLock, atomic_write
from .launch import launch_widget
from .store import Store
from .targets import Registry, claim_messages

COMMAND = '''---
description: Open or raise your local sticky board
allowed-tools: Bash(sticky:*)
disable-model-invocation: true
---
!`sticky widget --background`

The local sticky board has been requested. No note was sent automatically.
'''
log=logging.getLogger(__name__)


def _decode(value):
    return base64.b64decode(value) if value is not None else None


def _backup(path):
    return base64.b64encode(path.read_bytes()).decode() if path.exists() else None


def _restore(path,data):
    if data is None:
        path.unlink(missing_ok=True)
    else:
        atomic_write(path,data)


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _paths():
    return Path.home()/'.claude/settings.json',Path.home()/'.claude/commands/sticky.md',Store().home/'installs/claude.json'


def _entries(autostart):
    return {'SessionStart':{'hooks':[{'type':'command','command':'sticky claude-hook'+(' --autostart' if autostart else '')}]},
            'UserPromptSubmit':{'hooks':[{'type':'command','command':'sticky claude-hook'}]}}


def _remove_owned(settings,entries):
    hooks=settings.get('hooks',{})
    if not isinstance(hooks,dict):
        raise ValueError('Claude hooks must be a JSON object')
    for event,entry in entries.items():
        values=hooks.get(event,[])
        if not isinstance(values,list):
            raise ValueError('Claude hook events must be arrays')
        # Remove precisely the one entry we added, never another user's hook.
        if entry in values:
            values.remove(entry)
        if not values:
            hooks.pop(event,None)
    if not hooks:
        settings.pop('hooks',None)


def install(*,autostart=False):
    settings_path,command_path,journal=_paths()
    with FileLock(journal.parent/'claude.lock'):
        state=json.loads(journal.read_bytes()) if journal.exists() else None
        if state is None and command_path.exists():
            raise ValueError('A /sticky command already exists; it was not overwritten')
        data=settings_path.read_bytes() if settings_path.exists() else b'{}'
        settings=json.loads(data)
        if not isinstance(settings,dict):
            raise ValueError('Claude settings must be a JSON object')
        if state:
            if command_path.exists() and _hash(command_path.read_bytes())!=state['command_hash']:
                raise ValueError('Installed /sticky command changed; not overwriting user edits')
            _remove_owned(settings,state['entries'])
        hooks=settings.setdefault('hooks',{})
        if not isinstance(hooks,dict):
            raise ValueError('Claude hooks must be a JSON object')
        entries=_entries(autostart)
        for event,entry in entries.items():
            array=hooks.setdefault(event,[])
            if not isinstance(array,list):
                raise ValueError('Claude hook events must be arrays')
            if entry in array and state is None:
                raise ValueError('Sticky hook already exists outside this installer')
            array.append(entry)
        installed=(json.dumps(settings,ensure_ascii=False,indent=2)+'\n').encode()
        original: dict = state or {'settings_original':_backup(settings_path),'command_original':_backup(command_path)}
        original.update(entries=entries,settings_hash=_hash(installed),command_hash=_hash(COMMAND.encode()))
        # Backup/journal exists before either user-facing file changes.
        atomic_write(journal,json.dumps(original).encode())
        atomic_write(command_path,COMMAND.encode())
        atomic_write(settings_path,installed)
    return 'Claude hooks and /sticky installed (notes attach to the next message)'


def uninstall():
    settings_path,command_path,journal=_paths()
    with FileLock(journal.parent/'claude.lock'):
        if not journal.exists():
            return 'Claude adapter not installed'
        state=json.loads(journal.read_bytes())
        if command_path.exists() and _hash(command_path.read_bytes())!=state['command_hash']:
            raise ValueError('Installed /sticky command was edited; refusing to remove it')
        if settings_path.exists():
            data=settings_path.read_bytes()
            if _hash(data)==state['settings_hash']:
                _restore(settings_path,_decode(state['settings_original']))
            else:
                settings=json.loads(data)
                _remove_owned(settings,state['entries'])
                atomic_write(settings_path,(json.dumps(settings,ensure_ascii=False,indent=2)+'\n').encode())
        _restore(command_path,_decode(state['command_original']))
        journal.unlink()
    return 'Claude adapter removed; unrelated settings preserved'


def hook(payload,*,autostart=False):
    try:
        if not isinstance(payload,dict) or payload.get('hook_event_name') not in {'SessionStart','UserPromptSubmit'}:
            return {}
        store=Store()
        record=Registry(store.home).register('claude',payload['session_id'],cwd=payload.get('cwd'),transcript_path=payload.get('transcript_path'))
        if payload['hook_event_name']=='SessionStart':
            if autostart:
                launch_widget()
            return {}
        claims=list(claim_messages(store.home,record['target']))
        if not claims:
            return {}
        result={'hookSpecificOutput':{'hookEventName':'UserPromptSubmit','additionalContext':'\n\n'.join(c.message for c in claims)}}
        # The output is JSON-only. Never acknowledge before a serialisable result exists.
        json.dumps(result)
        for claim in claims:
            claim.ack()
        return result
    except Exception:
        log.exception('Sticky Claude hook skipped invalid input')
        return {}
