import json
import os
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
import pytest
from sticky_intent.store import Store
from sticky_intent.targets import Registry, enqueue, claim_messages, deliver_pending, send_note, pid_alive
from sticky_intent import clipboard


def test_register_and_refresh(tmp_path):
    r=Registry(tmp_path)
    x=r.register('hermes','ses-1',pid=os.getpid(),cwd='/repo',clock=100)
    assert x['target'] == f'hermes-{os.getpid()}'
    assert x['session_id']=='ses-1' and x['heartbeat']==100
    r.register('hermes','ses-1',pid=os.getpid(),cwd='/repo',clock=110)
    assert r.list(clock=110)[0]['started']==100


@pytest.mark.parametrize('kind,age,live', [('hermes',59,True),('hermes',61,False),('claude',43199,True),('claude',43201,False)])
def test_heartbeat_staleness(tmp_path,kind,age,live):
    r=Registry(tmp_path); x=r.register(kind,'s',pid=os.getpid() if kind=='hermes' else None,clock=100)
    assert bool(r.list(clock=100+age)) is live
    assert (tmp_path/'sessions'/f"{x['target']}.json").exists() is live


def test_dead_pid_cleaned(tmp_path,monkeypatch):
    r=Registry(tmp_path); r.register('hermes','s',pid=123,clock=100)
    monkeypatch.setattr(os,'kill',Mock(side_effect=ProcessLookupError()))
    assert r.list(clock=100)==[]


def test_permission_denied_pid_alive(monkeypatch):
    monkeypatch.setattr(os,'kill',Mock(side_effect=PermissionError()))
    assert pid_alive(123) is True


@pytest.mark.parametrize('session', ['../escape','bad/id','bad\\id',''])
def test_registry_no_traversal(tmp_path,session):
    with pytest.raises(ValueError): Registry(tmp_path).register('claude',session)


def test_outbox_context_and_atomic_claim_race(tmp_path):
    s=Store(tmp_path); n=s.add('my context')
    r=Registry(tmp_path); target=r.register('hermes','s',pid=os.getpid())['target']
    enqueue(s,n.id,target)
    barrier=threading.Barrier(2)
    def consume():
        barrier.wait(); return list(claim_messages(tmp_path,target))
    with ThreadPoolExecutor(2) as ex:
        futures=[ex.submit(consume) for _ in range(2)]
        claims=[c for f in futures for c in f.result()]
    assert len(claims)==1
    assert '📌 Note #1' in claims[0].message and 'my context' in claims[0].message
    claims[0].ack()
    assert list(claim_messages(tmp_path,target))==[]


def test_failed_injection_requeues(tmp_path):
    s=Store(tmp_path); s.add('retry')
    target=Registry(tmp_path).register('hermes','s',pid=os.getpid())['target']
    enqueue(s,1,target)
    assert deliver_pending(tmp_path,target,lambda text:False)==0
    messages=[]
    assert deliver_pending(tmp_path,target,lambda text:messages.append(text) or True)==1
    assert len(messages)==1 and deliver_pending(tmp_path,target,lambda text:True)==0


def test_send_requires_selection_if_multiple(tmp_path):
    s=Store(tmp_path); s.add('context'); r=Registry(tmp_path)
    r.register('claude','a'); r.register('claude','b')
    with pytest.raises(ValueError,match='session'):
        send_note(s,1,'claude')
    message=send_note(s,1,'claude',session='b')
    assert 'next message' in message
    assert len(list(claim_messages(tmp_path,'claude-b')))==1


def test_send_clipboard_universal_context(tmp_path,monkeypatch):
    s=Store(tmp_path); s.add('data'); write=Mock()
    monkeypatch.setattr(clipboard,'write_clipboard',write)
    assert 'Copied' in send_note(s,1,'clipboard')
    assert write.call_args.args[0] == 'Context from my notes (#1):\ndata'


@pytest.mark.parametrize('name,command', [('wl-paste','wl-paste'),('xclip','xclip'),('pbpaste','pbpaste'),('powershell','powershell')])
def test_clipboard_read_fallback(monkeypatch,name,command):
    monkeypatch.delenv('DISPLAY',raising=False); monkeypatch.delenv('WAYLAND_DISPLAY',raising=False)
    monkeypatch.setattr(clipboard.shutil,'which',lambda x:f'/fake/{x}' if x==name else None)
    runner=Mock(return_value=Mock(returncode=0,stdout='exact\n',stderr=''))
    monkeypatch.setattr(clipboard.subprocess,'run',runner)
    assert clipboard.read_clipboard()=='exact\n'
    assert command in runner.call_args.args[0][0]
    assert runner.call_args.kwargs.get('shell',False) is False


def test_clipboard_write_has_stdin_no_shell(monkeypatch):
    monkeypatch.delenv('DISPLAY',raising=False); monkeypatch.delenv('WAYLAND_DISPLAY',raising=False)
    monkeypatch.setattr(clipboard.shutil,'which',lambda x:'/fake/wl-copy' if x=='wl-copy' else None)
    runner=Mock(return_value=Mock(returncode=0,stdout='',stderr='')); monkeypatch.setattr(clipboard.subprocess,'run',runner)
    clipboard.write_clipboard('$(do not execute)')
    assert runner.call_args.kwargs['input']=='$(do not execute)'


def test_no_clipboard_clear_error(monkeypatch):
    monkeypatch.delenv('DISPLAY',raising=False); monkeypatch.delenv('WAYLAND_DISPLAY',raising=False)
    monkeypatch.setattr(clipboard.shutil,'which',lambda x:None)
    with pytest.raises(RuntimeError,match='No clipboard backend available') as error: clipboard.read_clipboard()
    assert type(error.value) is RuntimeError
