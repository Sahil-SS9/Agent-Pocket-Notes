import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import Mock
import pytest
from sticky_intent.store import Store
from sticky_intent.targets import Registry, claim_messages
from sticky_intent.instance import WidgetInstance
from sticky_intent.widget import Widget, tk

pytestmark=pytest.mark.gui


@pytest.fixture
def ui():
    assert os.getenv('DISPLAY'), 'GUI tests require xvfb-run, never the real display'
    root=tk.Tk(); store=Store(); widget=Widget(root,store)
    root.update()
    yield widget,store,root
    try: widget.close()
    except tk.TclError: pass


def test_new_button(ui):
    w,s,r=ui
    assert 'new' in w.buttons
    w.buttons['new'].invoke(); r.update()
    assert s.get(1).source=='widget' and w.selected.id==1


def test_paste_button_exact(ui):
    w,s,r=ui
    assert 'paste' in w.buttons
    r.clipboard_clear(); r.clipboard_append('pasted\nexactly')
    w.buttons['paste'].invoke(); r.update()
    assert s.get(1).body=='pasted\nexactly' and s.get(1).source=='clipboard'


def test_tabs_filter_and_search(ui):
    w,s,r=ui
    a=s.add('Alpha'); b=s.add('Beta',pin=True); c=s.add('Gamma'); s.update(c.id,status='done')
    w.refresh(); r.update()
    assert w.rows('inbox')==[a.id] and w.rows('pinned')==[b.id] and w.rows('done')==[c.id]
    w.search.set('beta'); w.refresh()
    assert w.rows('inbox')==[] and w.rows('pinned')==[b.id]


def test_pin_unpin_done_buttons(ui):
    w,s,r=ui; s.add('actions'); w.select(1)
    w.buttons['pin'].invoke(); r.update(); assert s.get(1).status=='pinned'
    w.buttons['pin'].invoke(); r.update(); assert s.get(1).status=='inbox'
    w.buttons['done'].invoke(); r.update(); assert s.get(1).status=='done'


def test_edit_autosaves_and_title_updates(ui):
    w,s,r=ui; s.add('old'); w.select(1)
    w.editor.delete('1.0','end'); w.editor.insert('1.0','edited title\nbody'); r.update()
    w.save()
    assert s.get(1).body=='edited title\nbody' and s.get(1).title=='edited title'


def test_external_changes_refresh_without_clobber(ui):
    w,s,r=ui; s.add('old'); w.select(1)
    s.update(1,body='changed elsewhere',research='done'); w.refresh(); r.update()
    assert w.editor.get('1.0','end-1c')=='changed elsewhere'
    assert 'done' in str(w.trees['inbox'].item('1')['values'])


def test_copy_button_tk_clipboard(ui):
    w,s,r=ui; s.add('copy exactly'); w.select(1)
    w.buttons['copy'].invoke(); r.update()
    assert r.clipboard_get()=='copy exactly'


def test_target_picker_labels_and_send(ui):
    w,s,r=ui; s.add('send from widget'); w.select(1)
    Registry(s.home).register('hermes','ses',pid=os.getpid(),cwd='/sandbox/project')
    Registry(s.home).register('claude','abc',cwd='/claude/project')
    w.buttons['send'].invoke(); r.update()
    picker=w.picker
    labels=[picker.tree.item(i)['values'][0] for i in picker.tree.get_children()]
    assert any('next message' in label for label in labels) and 'Clipboard' in labels
    target=next(i for i in picker.tree.get_children() if str(picker.tree.item(i)['values'][0]).startswith('Hermes'))
    picker.tree.selection_set(target); picker.send_button.invoke(); r.update()
    assert len(list(claim_messages(s.home,f'hermes-{os.getpid()}')))==1
    assert 'Queued #1' in w.status.get()


def test_research_menu_starts_runner_and_badge(ui,monkeypatch):
    import sticky_intent.widget as module
    w,s,r=ui; s.add('research'); w.select(1)
    def start(store,note_id,runner):
        store.update(note_id,research='running'); return {'log':'fake.log'}
    fake=Mock(side_effect=start); monkeypatch.setattr(module,'start_research',fake)
    w.research_menu.invoke(0); r.update()
    assert fake.call_args.args[2]=='hermes'
    assert s.get(1).research=='running' and 'running' in str(w.trees['inbox'].item('1')['values'])


def test_keyboard_new(ui):
    w,s,r=ui
    r.focus_force(); r.update(); r.event_generate('<Control-n>'); r.update()
    assert len(s.list('all'))==1


def test_geometry_remembered(ui):
    w,s,r=ui; r.geometry('420x600+20+30'); r.update(); w.close()
    state=json.loads((s.home/'widget-state.json').read_bytes())
    assert state['geometry']=='420x600+20+30'
    r2=tk.Tk(); w2=Widget(r2,s); r2.update()
    try: assert r2.geometry()==state['geometry']
    finally: w2.close()


def test_second_launch_raises_existing_fast(ui):
    w,s,r=ui
    instance=WidgetInstance(s.home)
    assert instance.acquire()
    instance.ready(); w.instance=instance
    start=time.perf_counter()
    result=subprocess.run([sys.executable,'-m','sticky_intent','widget','--if-not-running'],capture_output=True,text=True,timeout=3)
    elapsed=time.perf_counter()-start
    assert result.returncode==0,result.stderr
    assert elapsed<.1,elapsed
    deadline=time.monotonic()+1
    while time.monotonic()<deadline:
        r.update()
        state=json.loads((s.home/'widget-ready.json').read_bytes())
        if state.get('raises',0)>0: break
        time.sleep(.01)
    assert state.get('raises',0)>0


def test_conflicting_autosave_preserves_both_versions(ui):
    w,s,r=ui; s.add('before'); w.select(1)
    w.editor.delete('1.0','end'); w.editor.insert('1.0','unsaved edit'); r.update()
    s.update(1,body='external research'); w.save()
    assert s.get(1).body=='external research'
    assert any(n.body=='unsaved edit' for n in s.list('all'))


def test_all_controls_fit_default_window(ui):
    w,s,r=ui; s.add('layout'); w.select(1); r.update()
    assert r.winfo_width()>=360
    for name,button in w.buttons.items():
        x=button.winfo_rootx()-r.winfo_rootx(); y=button.winfo_rooty()-r.winfo_rooty()
        assert 0<=x and x+button.winfo_width()<=r.winfo_width(),name
        assert 0<=y and y+button.winfo_height()<=r.winfo_height(),name


def test_completed_research_updates_status_line(ui):
    w,s,r=ui; s.add('research'); s.update(1,research='running'); w.select(1)
    w.status.set('Research #1 with hermes is running')
    s.update(1,research='done',body='research\n\n## Research — hermes\nanswer')
    w.refresh(); r.update()
    assert 'done' in w.status.get().lower() and 'running' not in w.status.get().lower()


def test_long_list_title_uses_ellipsis(ui):
    w,s,r=ui; s.add('A very long note title that cannot fit into a compact note column'); w.select(1); r.update()
    value=w.trees['inbox'].item('1')['values'][0]
    assert value.endswith('…')


def test_target_labels_fit_and_keep_claude_delivery_semantics(ui):
    from sticky_intent.widget import font,ttk
    w,s,r=ui; s.add('target readability'); w.select(1)
    Registry(s.home).register('hermes','s',pid=os.getpid(),cwd='/a/very/long/path/to/a-project-name')
    Registry(s.home).register('claude','c',cwd='/another/very/long/path/to/the-project')
    w.open_picker(); r.update()
    tree=w.picker.tree
    face=font.Font(r,font=ttk.Style(r).lookup('Treeview','font'))
    labels=[str(tree.item(i)['values'][0]) for i in tree.get_children()]
    assert any('next message' in label for label in labels)
    assert all(face.measure(label)<=int(tree.column('target','width'))-8 for label in labels)
