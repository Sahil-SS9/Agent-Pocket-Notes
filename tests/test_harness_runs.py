"""Detached six-harness execution against labelled local fixtures only."""
import json
import os
from pathlib import Path
import sys
import time
import pytest
from sticky_intent.store import Store
from sticky_intent.harnesses import KINDS, save_options
from sticky_intent.runs import start_run, sessions, jobs, note_history, note_history_groups
from test_harnesses import SAMPLES


def fixture_harness(tmp_path,kind,mode='success'):
    file=tmp_path/(kind+'-fixture')
    file.write_text('#!'+sys.executable+'\n'+'''import sys,json,time
args=sys.argv[1:]
if '--help' in args:
    print('--query --query-file --toolsets --format --json --mode --session --resume --output-format --permission-mode --agent'); sys.exit(0)
if any(x in args for x in ['auth','status','login']):
    print(json.dumps({'loggedIn':MODE!='auth','status':'ready' if MODE!='auth' else 'not_ready'})); sys.exit(0)
if MODE=='error': print(json.dumps({'type':'error','error':'No access token found'})); sys.exit(1)
from pathlib import Path
payload=Path(args[args.index('--query-file')+1]).read_text() if '--query-file' in args else sys.stdin.read()
if not payload or 'this note' not in payload: print('Missing complete note input'); sys.exit(9)
if MODE=='slow': time.sleep(.4)
for record in RECORDS: print(json.dumps(record,ensure_ascii=False))
'''.replace('MODE',repr(mode)).replace('RECORDS',repr(SAMPLES[kind])))
    file.chmod(0o700); return file


def configure(tmp_path,store,kind,mode='success'):
    exe=fixture_harness(tmp_path,kind,mode)
    save_options(store,kind,dict(executable=str(exe),provider='fixture',model='fixture-model'))
    return exe


def completed(store,job,timeout=8) -> dict:
    path=Path(job['record']); deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        record=json.loads(path.read_text())
        if record['state'] in {'done','failed','cancelled'}: return record
        time.sleep(.02)
    raise AssertionError('Supervisor did not complete: '+str(path))


@pytest.mark.parametrize('kind',KINDS)
def test_new_run_appends_labelled_reply_and_resumes_explicit_session(tmp_path,kind):
    store=Store(); note=store.add('Original private thought\nKeep this exact text.')
    configure(tmp_path,store,kind)
    record=completed(store,start_run(store,note.id,kind))
    assert record['state']=='done',record
    body=store.get(note.id).body
    assert body.startswith(note.body+'\n\n') and 'FIXTURE ANSWER' in body
    assert record['session_id'] and record['job_id'] in body
    assert all(note.body not in argument for argument in record['argv'])
    assert note.body in Path(record['input_file']).read_text()
    available=sessions(store,kind)
    assert len(available)==1 and available[0]['session_id']==record['session_id']
    again=completed(store,start_run(store,note.id,kind,session=record['session_id']))
    assert again['state']=='done' and record['session_id'] in again['argv']
    assert store.get(note.id).body.count('## ✉ Reply —')==2
    assert not (store.home/'kanban').exists()


def test_note_history_derives_harness_and_session_from_real_run_records(tmp_path):
    """History is note-centred: it joins live run records to notes, not a session list."""
    store=Store()
    used=store.add('Sent this note to an agent\nBody line for the preview.')
    quiet=store.add('Never sent anywhere\nShould stay out of history.')
    configure(tmp_path,store,'hermes')
    record=completed(store,start_run(store,used.id,'hermes'))
    rows=note_history(store)
    assert [row['note_id'] for row in rows]==[used.id], rows
    row=rows[0]
    assert row['kind']=='hermes' and row['label']=='Hermes'
    assert row['session_id']==record['session_id'] and row['resumable'] is True
    assert row['replied'] is True and row['last_state']=='done'
    assert row['title']=='Sent this note to an agent'
    assert row['preview'].startswith('Sent this note to an agent')
    assert '✉' not in row['preview'] and 'FIXTURE ANSWER' not in row['preview']
    groups=note_history_groups(store)
    assert [group['kind'] for group in groups]==['hermes']
    assert groups[0]['count']==1 and [n['note_id'] for n in groups[0]['notes']]==[used.id]


def test_note_history_groups_a_note_under_every_harness_it_was_used_with(tmp_path):
    store=Store(); note=store.add('Shared across two harnesses\nBody')
    configure(tmp_path,store,'hermes')
    configure(tmp_path,store,'claude')
    completed(store,start_run(store,note.id,'hermes'))
    completed(store,start_run(store,note.id,'claude'))
    row=note_history(store)[0]
    assert set(row['harnesses'])=={'hermes','claude'}
    assert row['kind']=='claude', 'newest activity decides the card harness'
    groups={group['kind']:group for group in note_history_groups(store)}
    assert set(groups)=={'hermes','claude'}
    assert all(group['count']==1 for group in groups.values())
    assert all([n['note_id'] for n in group['notes']]==[note.id] for group in groups.values())


def test_note_history_skips_activity_whose_note_is_gone(tmp_path):
    store=Store()
    directory=store.home/'runs'; directory.mkdir(parents=True,exist_ok=True)
    payload=dict(job_id='ghost-job',note_id=424242,kind='hermes',state='done',
                 created='2026-01-01T00:00:00Z',session_id='ghost-session')
    (directory/'ghost-job.json').write_text(json.dumps(payload))
    assert [row['note_id'] for row in note_history(store) if row['note_id']==424242]==[]
    assert note_history_groups(store)==[group for group in note_history_groups(store) if group['count']]


def test_auth_preflight_refuses_before_run_and_leaves_note_exact(tmp_path):
    store=Store(); note=store.add('Never append login errors')
    configure(tmp_path,store,'claude','auth')
    with pytest.raises(ValueError,match='Sign in|readiness'): start_run(store,note.id,'claude',operation='research')
    assert store.get(note.id).body==note.body and store.get(note.id).research=='none'
    assert jobs(store)==[]


def test_failure_stays_in_receipt_and_log_not_body(tmp_path):
    store=Store(); note=store.add('Untouched on error')
    configure(tmp_path,store,'claude','error')
    record=completed(store,start_run(store,note.id,'claude',operation='research'))
    assert record['state']=='failed' and record['error']
    assert store.get(note.id).body==note.body
    assert store.get(note.id).research=='failed'
    assert 'No access token' in Path(record['log']).read_text()


def test_running_refuses_overlap_and_preserves_concurrent_edit(tmp_path):
    store=Store(); note=store.add('Original'); configure(tmp_path,store,'claude','slow')
    job=start_run(store,note.id,'claude')
    with pytest.raises(ValueError,match='running'): start_run(store,note.id,'claude')
    store.update(note.id,body='Edited while work runs')
    record=completed(store,job)
    assert record['state']=='done'
    assert store.get(note.id).body.startswith('Edited while work runs\n\n## ✉ Reply')


def test_unknown_existing_session_refused_before_execution(tmp_path):
    store=Store(); note=store.add('one'); configure(tmp_path,store,'claude')
    with pytest.raises(ValueError,match='session'): start_run(store,note.id,'claude',session='unrecorded-id')
    assert store.get(note.id).body==note.body and jobs(store)==[]


def test_interrupted_supervisor_does_not_leave_research_permanently_running(tmp_path):
    store=Store(); note=store.add('Recoverable original'); configure(tmp_path,store,'claude')
    store.update(note.id,research='running')
    directory=store.home/'runs'; directory.mkdir()
    path=directory/'interrupted.json'
    path.write_text(json.dumps(dict(job_id='interrupted',note_id=note.id,kind='claude',operation='research',created='2000-01-01T00:00:00Z',state='running',pid=99999999,record=str(path))))
    record=completed(store,start_run(store,note.id,'claude',operation='research'))
    assert record['state']=='done' and store.get(note.id).body.startswith('Recoverable original\n\n')
    assert json.loads(path.read_text())['state']=='failed'


def test_append_receipt_is_idempotent(tmp_path):
    from sticky_intent.runs import append_reply
    store=Store(); note=store.add('one'); configure(tmp_path,store,'claude')
    record=completed(store,start_run(store,note.id,'claude'))
    original=store.get(note.id).body
    assert append_reply(store,record,dict(text='DUPLICATE',session_id=record['session_id'])) is False
    assert store.get(note.id).body==original


@pytest.mark.parametrize('kind',KINDS)
def test_large_note_uses_complete_private_input_not_process_arguments(tmp_path,kind):
    store=Store(); text='Large private input\n'+'x'*160000
    note=store.add(text); configure(tmp_path,store,kind)
    record=completed(store,start_run(store,note.id,kind))
    assert record['state']=='done',record
    assert text in Path(record['input_file']).read_text()
    assert Path(record['input_file']).stat().st_mode&0o777==0o600
    assert all(text not in arg for arg in record['argv'])
    assert store.get(note.id).body.startswith(text+'\n\n')


