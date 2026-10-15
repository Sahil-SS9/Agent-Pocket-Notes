"""Actual Tk journeys for the reference-led redesign. Always run under Xvfb."""
import json
import os
from unittest.mock import Mock
import pytest
from sticky_intent.store import Store
from sticky_intent.widget import Widget, tk

pytestmark = pytest.mark.gui


@pytest.fixture
def ui():
    assert os.getenv('DISPLAY'), 'Use Xvfb, never the real display'
    root = tk.Tk()
    store = Store()
    widget = Widget(root, store)
    root.update()
    yield widget, store, root
    try:
        widget.close()
    except tk.TclError:
        pass


def test_autosave_preserves_caret_and_undo(ui):
    w, s, r = ui
    s.add('First line\nSecond line')
    w.select(1)
    w.editor.edit_reset()
    w.editor.insert('2.end', ' changed')
    w.editor.mark_set('insert', '2.4')
    r.update()
    w.save()
    assert w.editor.index('insert') == '2.4', 'Autosave must not reload the editor'
    assert s.get(1).body.endswith(' changed')
    w.editor.edit_undo()
    assert w.editor.get('1.0', 'end-1c') == 'First line\nSecond line'


def test_focus_is_same_editor_with_board_chrome_hidden(ui):
    w, s, r = ui
    s.add('Keep this exact draft')
    w.select(1)
    editor = w.editor
    geometry = r.geometry()
    assert 'focus' in w.buttons, 'A focus control is needed, not another note window'
    w.buttons['focus'].invoke()
    r.update()
    assert w.editor is editor and w.editor.winfo_ismapped()
    assert not w.notebook.winfo_ismapped()
    assert w.editor.get('1.0', 'end-1c') == 'Keep this exact draft'
    w.buttons['focus'].invoke()
    r.update()
    assert w.notebook.winfo_ismapped() and r.geometry() == geometry


def test_collapse_restores_exact_view_and_geometry(ui):
    w, s, r = ui
    s.add('Do not hide or discard my note')
    w.select(1)
    r.geometry('420x640+80+90')
    r.update()
    geometry = r.geometry()
    assert 'collapse' in w.buttons, 'Notes need a reversible header-only state'
    w.buttons['collapse'].invoke()
    r.update()
    assert r.winfo_height() < 100 and not w.editor.winfo_ismapped()
    assert s.get(1).body == 'Do not hide or discard my note'
    w.buttons['collapse'].invoke()
    r.update()
    assert r.geometry() == geometry and w.editor.winfo_ismapped()


def test_theme_and_selected_note_survive_reopen(ui):
    w, s, r = ui
    s.add('First'); s.add('Second')
    w.select(1)
    assert callable(getattr(w, 'set_theme', None)), 'Appearance must be a usable persisted control'
    w.set_theme('midnight')
    r.update()
    dark = w.editor.cget('background')
    w.close()
    root = tk.Tk(); reopened = Widget(root, s); root.update()
    try:
        assert reopened.selected.id == 1
        assert reopened.editor.cget('background') == dark
        reopened.set_theme('paper'); root.update()
        assert reopened.editor.cget('background') != dark
    finally:
        reopened.close()


def test_tab_switch_never_sends_a_hidden_selection(ui):
    w, s, r = ui
    s.add('Inbox'); pinned = s.add('Pinned', pin=True)
    w.select(1)
    w.notebook.select(w.tabs['pinned']); r.update()
    assert w.selected is not None and w.selected.id == pinned.id
    w.notebook.select(w.tabs['done']); r.update()
    assert w.selected is None and str(w.buttons['send'].cget('state')) == 'disabled'


def test_empty_search_is_helpful_and_new_clears_it(ui):
    w, s, r = ui
    s.add('A useful question'); w.select(1)
    w.search.set('no-such-note'); r.update()
    assert hasattr(w, 'empty_text'), 'No matches needs an explicit state, not a blank table'
    assert 'match' in w.empty_text.get().lower()
    assert w.selected is None
    w.buttons['new'].invoke(); r.update()
    assert w.search.get() == '' and w.selected.id == 2


def test_editor_native_paste_does_not_create_a_new_note(ui):
    w, s, r = ui
    s.add('Hello'); w.select(1)
    r.clipboard_clear(); r.clipboard_append(' world')
    w.editor.focus_force(); w.editor.mark_set('insert', 'end-1c'); r.update()
    w.editor.event_generate('<Control-v>'); r.update()
    assert len(s.list('all')) == 1, 'Ordinary editor paste must stay in the editor'
    assert w.editor.get('1.0', 'end-1c') == 'Hello world'
    w.save(); assert s.get(1).body == 'Hello world'


def test_capture_shortcut_creates_separate_note(ui):
    w, s, r = ui
    s.add('Original'); w.select(1)
    r.clipboard_clear(); r.clipboard_append('Separate thought')
    w.editor.focus_force(); r.update()
    w.editor.event_generate('<Control-Shift-V>'); r.update()
    assert len(s.list('all')) == 2 and w.selected.body == 'Separate thought'
    assert s.get(1).body == 'Original'


def test_search_shortcut_and_escape(ui):
    w, s, r = ui
    assert hasattr(w, 'search_entry'), 'Search needs a reachable keyboard surface'
    w.editor.focus_force(); r.update()
    w.editor.event_generate('<Control-f>'); r.update()
    assert r.focus_get() == w.search_entry
    w.search.set('abc'); w.search_entry.event_generate('<Escape>'); r.update()
    assert w.search.get() == ''


def test_running_research_cannot_spawn_duplicate(ui, monkeypatch):
    import sticky_intent.widget as module
    w, s, r = ui
    s.add('Research once'); w.select(1)
    def start(store, note_id, runner):
        store.update(note_id, research='running')
        return {'log': 'fixture-only.log'}
    fake = Mock(side_effect=start)
    monkeypatch.setattr(module, 'start_research', fake)
    w.research('hermes'); r.update(); w.research('hermes'); r.update()
    assert fake.call_count == 1
    assert str(w.buttons['research'].cget('state')) == 'disabled'


def test_save_failure_does_not_close_and_discard_draft(ui, monkeypatch):
    w, s, r = ui
    s.add('Before'); w.select(1)
    w.editor.insert('end-1c', ' unsaved'); r.update()
    def fail(*args, **kwargs):
        raise OSError('Sandbox disk unavailable')
    with monkeypatch.context() as patch:
        patch.setattr(s, 'update', fail)
        w.close()
        assert not w.closed and r.winfo_exists()
        assert w.editor.get('1.0', 'end-1c') == 'Before unsaved'
        assert 'unavailable' in w.status.get()
    w.save()


def test_picker_is_single_instance_and_closes_on_note_change(ui):
    w, s, r = ui
    s.add('One'); s.add('Two'); w.select(1)
    w.open_picker(); r.update(); first = w.picker
    w.open_picker(); r.update()
    assert w.picker is first, 'Repeated Send must raise the same picker'
    w.select(2); r.update()
    assert not first.window.winfo_exists(), 'A stale picker must not send a different note'


@pytest.mark.parametrize('geometry', ['360x520+0+0', '640x760+0+0'])
def test_visible_actions_fit_small_and_large_windows(ui, geometry):
    w, s, r = ui
    s.add('A note to read\nWith enough body text to edit.'); w.select(1)
    r.geometry(geometry); r.update()
    for name, button in w.buttons.items():
        if not button.winfo_ismapped():
            continue
        x = button.winfo_rootx() - r.winfo_rootx(); y = button.winfo_rooty() - r.winfo_rooty()
        assert x >= 0 and x + button.winfo_width() <= r.winfo_width(), name
        assert y >= 0 and y + button.winfo_height() <= r.winfo_height(), name
        assert button.winfo_height() >= 30, name


def test_corrupt_optional_ui_state_falls_back_without_crashing():
    store = Store(); store.add('Recover this note')
    (store.home / 'widget-state.json').write_text(json.dumps({'theme': [], 'last_target': [[], {}], 'geometry': {}}))
    root = tk.Tk()
    try:
        widget = Widget(root, store); root.update()
        assert widget.selected is not None and widget.selected.body == 'Recover this note'
        assert widget.theme == 'paper' and widget.last_target is None
        widget.close()
    finally:
        try: root.destroy()
        except tk.TclError: pass


def test_collapsed_header_keeps_research_state_visible(ui):
    w, s, r = ui
    s.add('Look this up'); w.select(1)
    assert 'collapse' in w.buttons
    w.buttons['collapse'].invoke(); r.update()
    s.update(1, research='running'); w.refresh(); r.update()
    assert 'researching' in str(w.brand.cget('text')).lower()
    s.update(1, research='done'); w.refresh(); r.update()
    assert 'done' in str(w.brand.cget('text')).lower()


def test_code_font_is_really_monospace(ui):
    from sticky_intent.widget import font
    w, s, r = ui
    s.add('Code snippet\n```python\nprint(123)\n```'); w.select(1)
    face = font.Font(r, font=w.editor.tag_cget('code', 'font'))
    assert face.measure('iii') == face.measure('WWW'), 'A named font is not a font family'


def test_external_trash_during_resize_never_raises_a_tk_callback(ui):
    w, s, r = ui
    s.add('Can be removed by the CLI'); w.select(1); r.update()
    callbacks = []
    r.report_callback_exception = lambda kind, value, trace: callbacks.append(value)
    s.delete(1)
    r.geometry('460x650+0+0'); r.update_idletasks()
    assert callbacks == [], 'Resize must not reopen files the CLI just moved to trash'
    w.refresh(); r.update()
    assert w.selected is None


@pytest.mark.parametrize('theme', ['paper', 'midnight'])
@pytest.mark.parametrize('state', [(), ('active',), ('pressed',)])
def test_primary_button_text_keeps_accessible_contrast_in_every_state(ui, theme, state):
    w, s, r = ui
    w.set_theme(theme); r.update()
    background = w.style.lookup('Primary.TButton', 'background', state=state)
    foreground = w.style.lookup('Primary.TButton', 'foreground', state=state)
    def luminance(value):
        rgb = [int(value[i:i+2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in rgb]
        return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))
    a, b = sorted((luminance(background), luminance(foreground)))
    assert (b + .05) / (a + .05) >= 4.5, (theme, state, background, foreground)
