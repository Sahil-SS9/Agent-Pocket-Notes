import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from sticky_intent.store import Store
from sticky_intent.targets import Registry, enqueue, claim_messages
from sticky_intent import claude_adapter as adapter


def test_install_merges_and_uninstall_byte_exact(sandbox):
    settings=sandbox/'.claude/settings.json'; settings.parent.mkdir()
    original=b'{\r\n  "other": true, "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "keep-me"}]}]}\r\n}\r\n'
    settings.write_bytes(original)
    adapter.install()
    installed=json.loads(settings.read_bytes())
    assert installed['other'] is True and installed['hooks']['Stop'][0]['hooks'][0]['command']=='keep-me'
    assert installed['hooks']['SessionStart'][0]['hooks'][0]['command']=='sticky claude-hook'
    assert installed['hooks']['UserPromptSubmit'][0]['hooks'][0]['command']=='sticky claude-hook'
    command=sandbox/'.claude/commands/sticky.md'
    assert '!`sticky widget --background`' in command.read_text()
    assert 'allowed-tools: Bash(sticky:*)' in command.read_text()
    adapter.uninstall()
    assert settings.read_bytes()==original and not command.exists()


def test_idempotent_install_and_autostart(sandbox):
    adapter.install(autostart=True); adapter.install(autostart=True)
    value=json.loads((sandbox/'.claude/settings.json').read_bytes())
    assert len(value['hooks']['SessionStart'])==1
    assert value['hooks']['SessionStart'][0]['hooks'][0]['command']=='sticky claude-hook --autostart'
    adapter.uninstall()
    assert not (sandbox/'.claude/settings.json').exists()


def test_preexisting_command_not_overwritten(sandbox):
    command=sandbox/'.claude/commands/sticky.md'; command.parent.mkdir(parents=True); command.write_text('mine')
    with pytest.raises(ValueError,match='already'):
        adapter.install()
    assert command.read_text()=='mine' and not (sandbox/'.claude/settings.json').exists()


def test_invalid_json_never_overwritten(sandbox):
    settings=sandbox/'.claude/settings.json'; settings.parent.mkdir(); settings.write_text('{broken')
    with pytest.raises(ValueError): adapter.install()
    assert settings.read_text()=='{broken'


def test_uninstall_preserves_subsequent_unrelated_edit(sandbox):
    adapter.install()
    settings=sandbox/'.claude/settings.json'; value=json.loads(settings.read_bytes()); value['theme']='mine'
    value['hooks']['SessionStart'].append({'hooks':[{'type':'command','command':'other'}]})
    settings.write_text(json.dumps(value))
    adapter.uninstall()
    final=json.loads(settings.read_bytes())
    assert final['theme']=='mine' and final['hooks']['SessionStart']==[{'hooks':[{'type':'command','command':'other'}]}]
    assert 'UserPromptSubmit' not in final.get('hooks',{})


def test_session_start_fixture_registers(sandbox):
    payload={'session_id':'abc-123','transcript_path':'/project/transcript.jsonl','cwd':'/project','permission_mode':'default','hook_event_name':'SessionStart','source':'startup','model':'claude-sonnet'}
    assert adapter.hook(payload)=={}
    record=Registry(Store().home).list()[0]
    assert record['kind']=='claude' and record['session_id']=='abc-123'
    assert record['cwd']=='/project' and record['transcript_path']==payload['transcript_path']


def test_prompt_fixture_injects_once(sandbox):
    s=Store(); s.add('look into this')
    payload={'session_id':'abc-123','transcript_path':'/project/transcript.jsonl','cwd':'/project','permission_mode':'default','hook_event_name':'UserPromptSubmit','prompt':'hi'}
    Registry(s.home).register('claude','abc-123'); enqueue(s,1,'claude-abc-123')
    output=adapter.hook(payload)
    specific=output['hookSpecificOutput']
    assert specific['hookEventName']=='UserPromptSubmit' and 'look into this' in specific['additionalContext']
    assert adapter.hook(payload)=={}


def test_autostart_only_on_session_start(monkeypatch):
    launch=Mock(); monkeypatch.setattr(adapter,'launch_widget',launch)
    adapter.hook({'hook_event_name':'SessionStart','session_id':'s','cwd':'/'},autostart=True)
    adapter.hook({'hook_event_name':'UserPromptSubmit','session_id':'s','cwd':'/'},autostart=True)
    assert launch.call_count==1


def test_bad_payload_quiet_no_session():
    assert adapter.hook({'hook_event_name':'SessionStart','session_id':'../bad'})=={}
    assert Registry(Store().home).list()==[]


def test_noop_uninstall():
    adapter.uninstall(); adapter.uninstall()
