import json
import os
from pathlib import Path
import sys
import time
import pytest
from sticky_intent.store import Store
from sticky_intent.research import start_research
from sticky_intent.cli import main


def runner(tmp_path,monkeypatch,kind='hermes',mode='success'):
    path=tmp_path/'bin'; path.mkdir(exist_ok=True)
    code={
       'success':'import sys; assert "Investigate the note" in sys.argv[-1]; print("Summary: useful answer\\nSource: https://example.org/fact")',
       'failed':'import sys; print("runner failure"); sys.exit(7)',
       'timeout':'import time; print("started",flush=True); time.sleep(30)',
       'empty':'pass',
    }[mode]
    exe=path/kind; exe.write_text(f'#!{sys.executable}\n'+code+'\n'); exe.chmod(0o700)
    monkeypatch.setenv('PATH',str(path)+os.pathsep+os.environ['PATH'])
    monkeypatch.setenv('STICKY_INTENT_NO_NOTIFICATIONS','1')
    return exe


def wait_for(store,status,timeout=8):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if store.get(1).research==status: return store.get(1)
        time.sleep(.02)
    pytest.fail(f'research never became {status}: {store.get(1)}')


@pytest.mark.parametrize('kind',['hermes','claude'])
def test_detached_fake_runner_success(tmp_path,monkeypatch,kind):
    runner(tmp_path,monkeypatch,kind)
    store=Store(); store.add('check this',pin=True)
    job=start_research(store,1,kind,timeout=2)
    assert job['pid'] != os.getpid() and job['runner']==kind
    note=wait_for(store,'done')
    assert note.status=='pinned' and note.body.startswith('check this\n\n## Research — '+kind)
    assert 'https://example.org/fact' in note.body
    assert Path(job['log']).read_text().strip().startswith('Summary: useful answer')


@pytest.mark.parametrize('mode',['failed','timeout','empty'])
def test_fake_runner_failure_and_timeout(tmp_path,monkeypatch,mode):
    runner(tmp_path,monkeypatch,mode=mode)
    store=Store(); store.add('investigate')
    job=start_research(store,1,'hermes',timeout=.15 if mode=='timeout' else 2)
    note=wait_for(store,'failed')
    assert '## Research — hermes' in note.body
    assert ('timed out' if mode=='timeout' else 'failed') in note.body.lower()
    assert Path(job['log']).exists()


def test_configurable_argv_no_shell(tmp_path,monkeypatch):
    store=Store(); store.add('{json} $(not-shell)')
    script=tmp_path/'custom.py'; script.write_text('import sys; print(sys.argv[-1])')
    config={'hermes':[sys.executable,str(script),'{prompt}']}
    (store.home/'config.toml').write_text('[research]\nhermes = '+json.dumps(config['hermes'])+'\ntimeout_seconds = 2\n')
    start_research(store,1,'hermes')
    note=wait_for(store,'done')
    assert '{json} $(not-shell)' in note.body


def test_second_job_refused_while_running(tmp_path,monkeypatch):
    runner(tmp_path,monkeypatch,mode='timeout'); store=Store(); store.add('one job')
    start_research(store,1,'hermes',timeout=.2)
    with pytest.raises(ValueError,match='running'): start_research(store,1,'hermes')
    wait_for(store,'failed')


def test_append_preserves_edit_made_during_research(tmp_path,monkeypatch):
    store=Store(); store.add('old')
    script=tmp_path/'slow.py'; script.write_text('import time; time.sleep(.3); print("answer")')
    (store.home/'config.toml').write_text('[research]\nhermes = '+json.dumps([sys.executable,str(script),'{prompt}']))
    start_research(store,1,'hermes',timeout=2)
    store.update(1,body='edited while running')
    assert wait_for(store,'done').body.startswith('edited while running\n\n## Research')


def test_missing_runner_has_failed_note(monkeypatch):
    monkeypatch.setenv('PATH','/does-not-exist'); store=Store(); store.add('missing runner')
    start_research(store,1,'hermes',timeout=2)
    note=wait_for(store,'failed')
    assert 'failed' in note.body.lower()


def test_research_cli_starts_fake_runner(tmp_path,monkeypatch,capsys):
    runner(tmp_path,monkeypatch); store=Store(); store.add('CLI research')
    assert main(['research','1','--with','hermes'])==0
    assert 'Research started' in capsys.readouterr().out
    wait_for(store,'done')
