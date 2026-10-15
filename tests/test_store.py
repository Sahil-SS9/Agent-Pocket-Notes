import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from sticky_intent.store import Store, default_home


def test_add_round_trip_exact_body(tmp_path):
    body = '  title: # literal\r\n---\r\n\nλ and 📌\n'
    s = Store(tmp_path / 'store')
    note = s.add(body, source='clipboard')
    assert note.id == 1
    assert s.get(1).body == body
    assert note.title == 'title: # literal'
    assert note.source == 'clipboard'
    assert note.status == 'inbox' and note.research == 'none'
    raw = (s.home / 'notes/1.md').read_bytes()
    assert raw.startswith(b'---\nid: 1\n') and raw.endswith(body.encode())


@pytest.mark.parametrize('platform,expected', [('linux','data/sticky-intent'), ('darwin','Library/Application Support/sticky-intent'), ('win32','roaming/sticky-intent')])
def test_platform_location(tmp_path, platform, expected):
    env = {'XDG_DATA_HOME':str(tmp_path/'data'), 'APPDATA':str(tmp_path/'roaming')}
    assert default_home(platform=platform, env=env, home=tmp_path) == tmp_path / expected


def test_home_override(tmp_path):
    assert default_home(env={'STICKY_INTENT_HOME':str(tmp_path/'chosen')}) == tmp_path/'chosen'


def test_pin_creation_and_reminder(tmp_path):
    n = Store(tmp_path/'s').add('first\nsecond', pin=True, remind='2026-10-14T09:00:00Z')
    assert n.status == 'pinned' and n.remind == '2026-10-14T09:00:00Z'
    assert n.created.endswith('Z') and n.updated == n.created


def test_empty_note_and_title_limit(tmp_path):
    s = Store(tmp_path/'s')
    assert s.add('').title == 'Untitled note'
    assert len(s.add('a'*120).title) == 80


@pytest.mark.parametrize('body', ['a'*(1024*1024+1), 'λ'*(1024*1024)], ids=['ascii-over-limit','utf8-byte-limit'])
def test_body_limit_bytes(tmp_path, body):
    with pytest.raises(ValueError, match='1 MB'):
        Store(tmp_path/'s').add(body)


@pytest.mark.parametrize('bad_id', ['../outside','-1','0','1.1',True])
def test_invalid_ids_refused(tmp_path, bad_id):
    with pytest.raises(ValueError, match='id'):
        Store(tmp_path/'s').get(bad_id)


def test_missing_note_error(tmp_path):
    with pytest.raises(FileNotFoundError, match='Note #9'):
        Store(tmp_path/'s').get(9)


def test_private_permissions(tmp_path):
    s = Store(tmp_path/'s')
    s.add('secret')
    if os.name != 'nt':
        assert (s.home.stat().st_mode & 0o777) == 0o700
        assert ((s.home/'notes/1.md').stat().st_mode & 0o777) == 0o600


def test_status_filters_and_search(tmp_path):
    s = Store(tmp_path/'s')
    a = s.add('alpha')
    b = s.add('BETA', pin=True)
    c = s.add('finished')
    s.update(c.id, status='done')
    assert [n.id for n in s.list()] == [a.id]
    assert [n.id for n in s.list('pinned', 'beta')] == [b.id]
    assert [n.id for n in s.list('done')] == [c.id]
    assert len(s.list('all')) == 3


def test_edit_preserves_metadata_and_changes_title(tmp_path):
    s = Store(tmp_path/'s')
    before = s.add('old', source='hermes')
    after = s.update(before.id, body='new\nbody')
    assert after.body == 'new\nbody' and after.title == 'new'
    assert after.created == before.created and after.updated != before.updated
    assert s.get(1) == after


def test_stale_editor_refuses_lost_update(tmp_path):
    s = Store(tmp_path/'s')
    old = s.add('original')
    s.update(1, body='research changed it')
    with pytest.raises(ValueError, match='changed'):
        s.update(1, body='stale edit', expected_updated=old.updated)
    assert s.get(1).body == 'research changed it'


@pytest.mark.parametrize('changes', [{'status':'oops'}, {'research':'oops'}, {'source':'email'}, {'title':'line\ninjection'}])
def test_invalid_metadata(tmp_path, changes):
    s = Store(tmp_path/'s')
    s.add('keep')
    with pytest.raises(ValueError):
        s.update(1, **changes)
    assert s.get(1).body == 'keep'


def test_atomic_failure_keeps_original_and_cleans_temp(tmp_path, monkeypatch):
    s = Store(tmp_path/'s')
    s.add('keep')
    real_replace = os.replace
    def fail(src, dst):
        if Path(dst).name == '1.md':
            raise OSError('simulated power boundary')
        return real_replace(src, dst)
    monkeypatch.setattr(os, 'replace', fail)
    with pytest.raises(OSError, match='boundary'):
        s.update(1, body='lost')
    assert s.get(1).body == 'keep'
    assert [p.name for p in (s.home/'notes').iterdir()] == ['1.md']


def test_trash_and_non_reused_ids(tmp_path):
    s = Store(tmp_path/'s')
    s.add('keep in trash')
    destination = s.delete(1)
    assert destination.read_text().endswith('keep in trash')
    assert s.list('all') == []
    assert s.add('second').id == 2


def test_header_strings_do_not_inject_fields(tmp_path):
    s = Store(tmp_path/'s')
    n = s.add('title: yes # no\n---\nstatus: done')
    assert s.get(n.id).title == 'title: yes # no'
    assert s.get(n.id).status == 'inbox'


def test_fifty_processes_unique_intact_ids(tmp_path):
    directory = str(tmp_path/'concurrent')
    code = 'from sticky_intent.store import Store; import sys; s=Store(sys.argv[1]); print(s.add(sys.argv[2]+"\\n"+"x"*10000).id)'
    children = [subprocess.Popen([sys.executable,'-c',code,directory,str(i)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for i in range(50)]
    results = [c.communicate(timeout=30) for c in children]
    assert all(c.returncode == 0 for c in children), results
    ids = [int(out) for out,err in results]
    assert len(set(ids)) == 50
    s = Store(directory)
    assert len(s.list('all')) == 50
    for i,note_id in enumerate(ids):
        assert s.get(note_id).body == str(i)+'\n'+'x'*10000
