"""Documented harness protocol fixtures; no real agents or credentials."""
import json
import pytest
from sticky_intent.harnesses import KINDS, build_command, parse_reply, connection

SAMPLES={
'hermes':[{'type':'system','subtype':'init','session_id':'hermes-fixture'},{'type':'result','session_id':'hermes-fixture','exit_code':0,'text':'HERMES FIXTURE ANSWER'}],
'claude':[{'type':'result','subtype':'success','is_error':False,'session_id':'claude-fixture','result':'CLAUDE FIXTURE ANSWER'}],
'codex':[{'type':'thread.started','thread_id':'codex-fixture'},{'type':'item.completed','item':{'type':'agent_message','text':'CODEX FIXTURE ANSWER'}},{'type':'turn.completed','usage':{}}],
'pi':[{'type':'session','id':'pi-fixture'},{'type':'message_end','message':{'role':'assistant','content':[{'type':'text','text':'PI FIXTURE ANSWER'}],'stopReason':'stop'}},{'type':'agent_settled','aborted':False}],
'command-code':[{'type':'result','subtype':'success','sessionId':'command-fixture','finalText':'COMMAND FIXTURE ANSWER'}],
'opencode':[{'type':'text','sessionID':'open-fixture','part':{'text':'OPENCODE FIXTURE ANSWER'}},{'type':'step_finish','sessionID':'open-fixture','part':{'reason':'stop'}}],
}

@pytest.mark.parametrize('kind',KINDS)
def test_documented_success_and_resume_argv(kind):
    prompt='Exact context $(never a shell)\nUnicode\u2028line'
    argv=build_command(kind,prompt,{'executable':'/fixture/'+kind,'model':'exact-model'},session='fixture-existing')
    assert argv[0]=='/fixture/'+kind and prompt in argv and 'fixture-existing' in argv
    assert '--yolo' not in argv and '--dangerously-skip-permissions' not in argv
    reply=parse_reply(kind,'\n'.join(json.dumps(x) for x in SAMPLES[kind]))
    assert reply['success'] and 'FIXTURE ANSWER' in reply['text'] and reply['session_id']

@pytest.mark.parametrize('kind',KINDS)
def test_process_failure_never_becomes_successful_reply(kind):
    output='\n'.join(json.dumps(x) for x in SAMPLES[kind])
    reply=parse_reply(kind,output,exit_code=1)
    assert not reply['success'] and reply['text']==''

@pytest.mark.parametrize('kind',KINDS)
def test_empty_or_nonprotocol_output_cannot_write_back(kind):
    assert not parse_reply(kind,'plain plausible text, not a supported event')['success']
    assert not parse_reply(kind,'')['success']

@pytest.mark.parametrize('kind',KINDS)
def test_missing_executable_is_unavailable_not_logged_out(kind):
    status=connection(kind,{'executable':'/missing/'+kind})
    assert status['state']=='not_installed' and not status['can_run']
    assert 'not found' in status['reason'].lower()


def test_visual_review_mode_reports_disabled_without_probing_cli(monkeypatch):
    monkeypatch.setenv('STICKY_INTENT_REVIEW_MODE','1')
    def forbidden(*args,**kwargs):
        raise AssertionError('visual review must not probe or execute an agent CLI')
    monkeypatch.setattr('sticky_intent.harnesses.subprocess.run',forbidden)
    monkeypatch.setattr('sticky_intent.harnesses.shutil.which',forbidden)
    for kind in KINDS:
        status=connection(kind,probe=True)
        assert status['state']=='review_only'
        assert not status['can_run'] and not status['executable']
        assert 'nothing was run' in status['reason']


def test_missing_capability_lists_exact_flags_and_refuses_to_run(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.delenv('STICKY_INTENT_REVIEW_MODE',raising=False)
    monkeypatch.setattr('sticky_intent.harnesses.resolve_executable',lambda kind,options:'/fixture/'+kind)
    monkeypatch.setattr('sticky_intent.harnesses.environment',lambda kind,options:{})
    monkeypatch.setattr('sticky_intent.harnesses.subprocess.run',lambda *args,**kwargs:SimpleNamespace(returncode=0,stdout='--help --format --query',stderr=''))
    status=connection('hermes',{'executable':'/fixture/hermes'},probe=True)
    assert status['state']=='unsupported_version' and not status['can_run']
    assert '--query-file' in status['reason'] and '--toolsets' in status['reason']


def test_structured_error_and_pi_abort_are_not_success():
    for kind in ['hermes','claude','command-code']:
        assert not parse_reply(kind,json.dumps({'type':'result','exit_code':1,'is_error':True,'subtype':'error','error':'auth_required'}))['success']
    records=SAMPLES['pi'][:-1]+[{'type':'agent_settled','aborted':True}]
    assert not parse_reply('pi','\n'.join(json.dumps(x) for x in records))['success']


def test_resume_identifier_cannot_be_a_cli_option():
    for kind in KINDS:
        with pytest.raises(ValueError): build_command(kind,'prompt',session='--yolo')


def test_incomplete_streams_are_not_completed_answers():
    for kind in ['hermes','codex','pi','opencode']:
        output='\n'.join(json.dumps(x) for x in SAMPLES[kind][:-1])
        assert not parse_reply(kind,output)['success']


@pytest.mark.parametrize('kind',KINDS)
def test_malformed_event_type_is_a_failure_not_an_exception(kind):
    assert not parse_reply(kind,json.dumps({'type':{'invalid':'object'}}))['success']


def test_pi_retry_can_recover_but_incomplete_tool_turn_cannot_finish():
    retry=[{'type':'session','id':'pi-fixture'},{'type':'message_end','message':{'role':'assistant','content':[],'stopReason':'error','errorMessage':'temporary overload'}}]+SAMPLES['pi'][1:]
    assert parse_reply('pi','\n'.join(json.dumps(x) for x in retry))['success']
    incomplete=[{'type':'message_end','message':{'role':'assistant','content':[{'type':'text','text':'About to call a tool'}],'stopReason':'toolUse'}},{'type':'agent_settled','aborted':False}]
    assert not parse_reply('pi','\n'.join(json.dumps(x) for x in incomplete))['success']


@pytest.mark.parametrize('kind',KINDS)
def test_fatal_event_cannot_be_erased_by_a_later_success_record(kind):
    stream=[{'type':'error','error':'fatal fixture'}]+SAMPLES[kind]
    assert not parse_reply(kind,'\n'.join(json.dumps(x) for x in stream))['success']
