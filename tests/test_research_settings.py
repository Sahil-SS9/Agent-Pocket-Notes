"""Explicit operator research configuration and auth recovery; no real agent calls."""
import json
import os
import sys
from pathlib import Path
from sticky_intent.store import Store
from sticky_intent.research import research_config, start_research
from test_research import wait_for


def test_hermes_profile_provider_and_model_are_used_without_shell():
    store=Store()
    (store.home/'config.toml').write_text('[research.hermes_options]\nexecutable = "/fixture/hermes"\nprofile = "research"\nprovider = "openai-codex"\nmodel = "my-exact-model"\n')
    argv,seconds=research_config(store,'hermes')
    assert argv == ['/fixture/hermes','--profile','research','chat','-Q','--provider','openai-codex','--model','my-exact-model','-q','{prompt}']


def test_auth_failure_has_account_specific_recovery(tmp_path,monkeypatch):
    store=Store(); store.add('Operator auth reproduction')
    script=tmp_path/'auth_fixture.py'
    script.write_text('import sys; print("No access token found for Nous Portal login. Run `hermes model` to re-authenticate."); sys.exit(1)')
    (store.home/'config.toml').write_text('[research]\nhermes = '+json.dumps([sys.executable,str(script),'{prompt}'])+'\n[research.hermes_options]\nprofile = "research"\n')
    job=start_research(store,1,'hermes',timeout=2)
    note=wait_for(store,'failed')
    # Note append and final job record are two atomic writes. Wait for the
    # supervisor's completion record, not merely the earlier note status.
    import time
    record_path=Path(str(job['log'])).with_suffix('.json')
    deadline=time.monotonic()+3
    while True:
        record=json.loads(record_path.read_text())
        if record['state'] in {'done','failed'} or time.monotonic()>=deadline: break
        time.sleep(.01)
    assert record['state']=='failed'
    assert record['failure_kind']=='authentication'
    assert '--profile research model' in note.body
    assert 'same desktop account' in note.body
    assert 'No access token found' in Path(job['log']).read_text()


def test_hermes_home_is_passed_to_runner(tmp_path):
    home=tmp_path/'chosen-hermes'; home.mkdir()
    store=Store(); store.add('Read configured account home')
    script=tmp_path/'environment_fixture.py'
    script.write_text('import os; print("HERMES_HOME="+os.environ["HERMES_HOME"])')
    (store.home/'config.toml').write_text('[research]\nhermes = '+json.dumps([sys.executable,str(script),'{prompt}'])+'\n[research.hermes_options]\nhome = '+json.dumps(str(home))+'\n')
    start_research(store,1,'hermes',timeout=2)
    assert 'HERMES_HOME='+str(home) in wait_for(store,'done').body


def test_research_settings_save_preserves_custom_argv_and_other_config():
    from sticky_intent.research import save_hermes_options, hermes_options
    store=Store()
    original='[unrelated]\nkeep = "yes"\n[research]\nhermes = ["/fixture/custom", "{prompt}"]\ntimeout_seconds = 42\n'
    (store.home/'config.toml').write_text(original)
    save_hermes_options(store,{'profile':'research','provider':'openai-codex','model':'exact','executable':'hermes','home':''})
    assert (store.home/'config.toml').read_text().startswith(original)
    assert research_config(store,'hermes') == (['/fixture/custom','{prompt}'],42)
    assert hermes_options(store)['profile']=='research'
    save_hermes_options(store,{'profile':'different'})
    assert hermes_options(store)['profile']=='different'
    assert research_config(store,'hermes')[0]==['/fixture/custom','{prompt}']
