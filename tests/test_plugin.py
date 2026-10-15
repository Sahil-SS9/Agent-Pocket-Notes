import os
import time
import subprocess
import sys
import pytest
from sticky_intent.store import Store
from sticky_intent.targets import Registry, enqueue
from sticky_intent.hermes_plugin import SessionBridge

class FakeCtx:
    def __init__(self):
        self.messages=[]; self.hooks={}; self.cleanups=[]; self.commands={}; self.tools={}; self.references=[]
    def inject_message(self,content,role='user',*,session_key=None,origin=None):
        assert session_key is None and origin is None
        self.messages.append(content); return True
    def on_unload(self,callback): self.cleanups.append(callback)
    def register_hook(self,name,callback): self.hooks[name]=callback
    def register_command(self,name,handler,description='',args_hint=''): self.commands[name]=handler
    def register_tool(self,name,toolset,schema,handler,**kwargs): self.tools[name]=(toolset,schema,handler)
    def register_context_reference(self,provider): self.references.append(provider)
    def get_config(self,key,default=None): return default


def test_bridge_watcher_injects_and_unloads(tmp_path):
    s=Store(tmp_path); s.add('bridge context'); ctx=FakeCtx()
    bridge=SessionBridge(ctx,s,interval=0.02)
    try:
        bridge.on_start(session_id='ses-1',platform='cli',model='local')
        target=Registry(s.home).list()[0]['target']; enqueue(s,1,target)
        deadline=time.monotonic()+2
        while not ctx.messages and time.monotonic()<deadline: time.sleep(0.01)
        assert len(ctx.messages)==1 and 'bridge context' in ctx.messages[0]
        assert ctx.cleanups and bridge.thread.daemon
    finally: bridge.stop()
    assert not bridge.thread.is_alive() and Registry(s.home).list()==[]


@pytest.mark.parametrize('platform',['telegram','discord','tui','desktop'])
def test_bridge_excludes_non_cli(tmp_path,platform):
    s=Store(tmp_path); bridge=SessionBridge(FakeCtx(),s,interval=0.02)
    try:
        bridge.on_start(session_id='s',platform=platform)
        assert Registry(s.home).list()==[] and bridge.thread is None
    finally: bridge.stop()


def test_plugin_import_never_imports_tk():
    code='import sys; import sticky_intent.hermes_plugin; assert "tkinter" not in sys.modules; assert "sticky_intent.widget" not in sys.modules'
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


class ReferenceBase:
    pass


def test_one_shot_cli_without_repl_not_advertised(tmp_path):
    from types import SimpleNamespace
    ctx=FakeCtx(); setattr(ctx,'_manager',SimpleNamespace(_cli_ref=None))
    store=Store(tmp_path); bridge=SessionBridge(ctx,store)
    try:
        bridge.on_start(session_id='one-shot',platform='cli')
        assert Registry(store.home).list()==[] and bridge.thread is None
    finally: bridge.stop()


class Completion:
    def __init__(self,text,display='',meta=''):
        self.text=text; self.display=display; self.meta=meta


@pytest.fixture
def registered():
    from sticky_intent.hermes_plugin import register
    ctx=FakeCtx()
    bridge=register(ctx,reference_api=(ReferenceBase,Completion))
    yield ctx,bridge,Store()
    bridge.stop()


def test_register_command_reference_and_tool(registered):
    ctx,bridge,store=registered
    assert set(ctx.commands)=={'sticky'}
    assert ctx.references[0].prefix=='note' and isinstance(ctx.references[0],ReferenceBase)
    toolset,schema,handler=ctx.tools['sticky_notes']
    assert toolset=='sticky' and schema['parameters']['required']==['action']
    assert schema['parameters']['properties']['action']['enum']==['search','get','add','pin','list']


def test_reference_autocomplete_and_expand(registered):
    import asyncio
    ctx,bridge,store=registered
    store.add('Alpha'); store.add('Beta')
    ref=ctx.references[0]
    items=asyncio.run(ref.autocomplete('alpha',limit=1))
    assert len(items)==1 and items[0].text=='@note:1'
    assert 'Alpha' in asyncio.run(ref.expand('1'))
    assert asyncio.run(ref.expand('999')) is None


def test_tool_actions_persist(registered):
    import json
    ctx,bridge,store=registered
    handle=ctx.tools['sticky_notes'][2]
    result=json.loads(handle({'action':'add','body':'remember this'}))
    assert result['success'] and store.get(1).source=='hermes'
    assert json.loads(handle({'action':'pin','id':1}))['success']
    assert store.get(1).status=='pinned'
    assert json.loads(handle({'action':'get','id':1}))['note']['body']=='remember this'
    assert len(json.loads(handle({'action':'search','query':'remember'}))['notes'])==1
    assert len(json.loads(handle({'action':'list','status':'pinned'}))['notes'])==1
    assert json.loads(handle({'action':'get','id':999}))['success'] is False


def test_slash_subcommands_and_direct_send(registered):
    ctx,bridge,store=registered
    command=ctx.commands['sticky']
    assert '#1' in command('add slash context')
    assert 'slash context' in command('list')
    command('pin 1'); assert store.get(1).status=='pinned'
    command('done 1'); assert store.get(1).status=='done'
    assert 'Sent' in command('send 1') and 'slash context' in ctx.messages[-1]
    assert 'sticky:' in command('send bad')


def test_headless_slash_text_fallback(registered,monkeypatch):
    ctx,bridge,store=registered; store.add('headless')
    monkeypatch.delenv('DISPLAY',raising=False); monkeypatch.delenv('WAYLAND_DISPLAY',raising=False)
    result=ctx.commands['sticky']('')
    assert 'headless' in result and 'display' in result.lower()


def test_gui_launch_failure_text_fallback(registered,monkeypatch):
    import sticky_intent.hermes_plugin as plugin
    ctx,bridge,store=registered; store.add('fallback')
    monkeypatch.setattr(plugin,'has_display',lambda:True)
    monkeypatch.setattr(plugin,'launch_widget',lambda **kw:(False,'Tk cannot access display'))
    result=ctx.commands['sticky']('')
    assert 'fallback' in result and 'Tk cannot access display' in result


def test_resumed_cli_registration_via_pre_llm(registered):
    ctx,bridge,store=registered
    ctx.hooks['pre_llm_call'](session_id='resumed',platform='cli')
    assert Registry(store.home).list()[0]['session_id']=='resumed'


@pytest.mark.slow
def test_real_upstream_directory_load_and_registry(tmp_path):
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    run_dir=os.environ.get('STICKY_INTENT_HERMES_RUN','')
    run=Path(run_dir) if run_dir else None
    if run is None or not run.is_dir(): pytest.skip('set STICKY_INTENT_HERMES_RUN to a disposable upstream run directory')
    code='''import sys,os,json,asyncio,queue,shutil
from pathlib import Path
root=Path(sys.argv[1]); home=Path(os.environ['HERMES_HOME']); dest=home/'plugins/sticky-intent'
shutil.copytree(root,dest,ignore=shutil.ignore_patterns('.git','.venv','__pycache__','.pytest_cache','*.egg-info','build','dist'))
home.mkdir(parents=True,exist_ok=True)
(home/'config.yaml').write_text('plugins:\\n  enabled: [sticky-intent]\\n')
import subprocess
listing=subprocess.run([sys.executable,'-m','hermes_cli.main','plugins','list'],capture_output=True,text=True,timeout=30)
assert listing.returncode==0 and 'sticky-intent' in listing.stdout,listing.stdout+listing.stderr
from hermes_cli.plugins import PluginManager
from tools.registry import registry
from agent.context_references import get_context_reference_providers
manager=PluginManager(); manager.discover_and_load()
loaded=manager._plugins['sticky-intent']; assert loaded.enabled and not loaded.error,loaded.error
scope=manager.scope_key
reply=json.loads(registry.dispatch('sticky_notes',{'action':'add','body':'native host note'},scope=scope)); assert reply['success'],reply
reply=json.loads(registry.dispatch('sticky_notes',{'action':'get','id':1},scope=scope)); assert reply['note']['body']=='native host note',reply
assert 'error' in registry.dispatch('sticky_missing',{},scope=scope).lower()
ref=get_context_reference_providers()['note']; assert 'native host note' in asyncio.run(ref.expand('1'))
assert 'sticky' in manager._plugin_commands
assert 'tkinter' not in sys.modules
from types import SimpleNamespace
manager._cli_ref=SimpleNamespace(_pending_input=queue.Queue(),_interrupt_queue=queue.Queue(),_agent_running=False)
command=manager._plugin_commands['sticky']['handler']; assert 'Sent' in command('send 1')
assert 'native host note' in manager._cli_ref._pending_input.get_nowait()
manager.unload()
print('NATIVE PLUGIN PASS')'''
    env=os.environ.copy(); env['HERMES_HOME']=str(tmp_path/'hermes-home')
    env['PYTHONDONTWRITEBYTECODE']='1'
    result=subprocess.run([str(run/'host-venv/bin/python'),'-c',code,str(root)],env=env,cwd=run/'host',capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert 'NATIVE PLUGIN PASS' in result.stdout
