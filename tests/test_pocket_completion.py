import json
import os
import sys
import time
import pytest
from sticky_intent.store import Store
from sticky_intent.pocket import PocketController


def test_preferences_capture_and_geometry_survive_restart(tmp_path):
    c = PocketController(Store(tmp_path))
    c.set_preference('theme', 'retro')
    c.set_preference('font_family', 'DejaVu Serif')
    c.set_preference('text_size', 25)
    c.set_preference('interface_size', 200)
    c.set_preference('on_top', True)
    c.set_preference('styled_text', True)
    c.capture_draft = 'Exact\r\n  capture\n'
    c.geometries['notes'] = [40, 60, 500, 600]
    assert c.transition('capture')
    assert c.transition('icon')
    assert c.close()
    again = PocketController(Store(tmp_path))
    assert again.capture_draft == 'Exact\r\n  capture\n'
    assert again.mode == 'icon' and again.icon_restore == 'capture'
    assert again.preferences['font_family'] == 'DejaVu Serif'
    assert again.preferences['text_size'] == 25
    assert again.preferences['interface_size'] == 200
    assert again.preferences['theme'] == 'retro'
    assert again.geometries['notes'] == [40, 60, 500, 600]
    assert (tmp_path / 'pocket-state.json').stat().st_mode & 0o777 == 0o600


def test_empty_board_editor_autosaves_and_new_note_does_not_overwrite(tmp_path):
    c = PocketController(Store(tmp_path))
    c.body = 'First\n  exact'
    assert c.save()
    original = c.selected.id
    assert c.new_note()
    c.body = 'Second'
    assert c.save()
    assert c.store.get(original).body == 'First\n  exact'
    assert c.selected.id != original


def test_refresh_only_replaces_clean_text_and_keep_both_resolves_conflict(tmp_path):
    s = Store(tmp_path); n = s.add('Initial')
    c = PocketController(s); c.select(n.id)
    s.update(n.id, body='Research result', research='done')
    assert c.refresh() and c.body == 'Research result'
    c.body = 'Local unsaved'
    s.update(n.id, body='External')
    assert not c.save()
    assert c.conflict and c.body == 'Local unsaved'
    assert c.keep_both()
    assert s.get(n.id).body == 'External'
    assert c.selected.id != n.id and c.selected.body == 'Local unsaved'


def test_state_failure_blocks_hide_and_close(tmp_path, monkeypatch):
    import sticky_intent.pocket as module
    c = PocketController(Store(tmp_path))
    c.capture_draft = 'Only draft'
    def fail(*a, **k): raise OSError('State disk full')
    monkeypatch.setattr(module, 'atomic_write', fail)
    assert not c.transition('icon') and c.mode == 'notes'
    assert not c.close()
    assert c.capture_draft == 'Only draft'
    assert 'disk full' in c.error


def test_session_queue_last_target_and_research_round_trip(tmp_path):
    from sticky_intent.targets import Registry, claim_messages
    s = Store(tmp_path); n = s.add('Investigate $(no-shell)')
    c = PocketController(s); c.select(n.id)
    Registry(tmp_path).register('hermes', 'fixture-session', pid=os.getpid(), cwd='/sandbox')
    assert c.send('hermes', 'fixture-session')
    messages = list(claim_messages(tmp_path, f'hermes-{os.getpid()}'))
    assert len(messages) == 1 and 'Investigate $(no-shell)' in messages[0].message
    messages[0].ack()
    assert c.last_target == ['hermes', 'fixture-session']
    script = tmp_path/'runner.py'
    script.write_text('import time; time.sleep(.15); print("Fixture answer — not a real agent call")')
    (tmp_path/'config.toml').write_text('[research]\nhermes = '+json.dumps([sys.executable,str(script),'{prompt}'])+'\ntimeout_seconds = 2\n')
    assert c.research('hermes')
    assert not c.research('hermes')
    deadline = time.monotonic()+5
    while time.monotonic()<deadline and s.get(n.id).research == 'running': time.sleep(.02)
    c.refresh()
    assert c.selected.research == 'done'
    assert 'Fixture answer' in c.body
    assert c.research_logs() and c.research_logs()[0]['path'].endswith('.log')


def test_legacy_appearance_import_and_invalid_preferences(tmp_path):
    (tmp_path/'widget-state.json').write_text(json.dumps({'theme':'midnight','font_family':'Noto Serif','text_size':125,'interface_size':150}))
    c = PocketController(Store(tmp_path))
    assert c.preferences['theme'] == 'midnight'
    assert c.preferences['font_family'] == 'Noto Serif'
    for name,value in [('text_size',24),('interface_size',201),('theme','bad'),('on_top','yes')]:
        with pytest.raises(ValueError): c.set_preference(name,value)


def test_capture_state_failure_does_not_duplicate_saved_note(tmp_path,monkeypatch):
    import sticky_intent.pocket as module
    s=Store(tmp_path); c=PocketController(s); c.mode='capture'; c.capture_draft='Exact saved once'
    original=module.atomic_write
    def fail(*a,**k): raise OSError('State disk full')
    monkeypatch.setattr(module,'atomic_write',fail)
    assert not c.capture_save()
    assert c.mode=='capture' and c.capture_draft=='Exact saved once'
    assert len(s.list('all'))==1
    monkeypatch.setattr(module,'atomic_write',original)
    assert c.capture_save()
    assert c.mode=='icon' and c.capture_draft==''
    assert len(s.list('all'))==1


def test_delete_disabled_empty_and_moves_note_to_trash(tmp_path):
    c = PocketController(Store(tmp_path))
    assert not c.delete_note()
    assert c.new_note()
    note_id = c.selected.id
    c.body = 'Before trash'; c.save()
    assert c.delete_note()
    assert (tmp_path/'trash'/f'{note_id}.md').exists()
    assert c.selected is None
