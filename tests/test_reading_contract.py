"""Owner-approved typography contract, exercised only under isolated Xvfb."""
import pytest
from sticky_intent.store import Store
from sticky_intent.widget import Widget, tk, font

pytestmark = pytest.mark.gui

@pytest.fixture(params=[96, 144, 288])
def ui(request):
    root = tk.Tk()
    original = float(root.tk.call('tk', 'scaling'))
    root.tk.call('tk', 'scaling', request.param / 72)
    store = Store()
    store.add('Ordinary first line\n## Still plain text\n' + 'Comfortable wrapped reading. ' * 35)
    w = Widget(root, store)
    root.update()
    w.select(1)
    yield w, root
    w.close()
    reset = tk.Tk(); reset.withdraw()
    reset.tk.call('tk', 'scaling', original); reset.destroy()

def resolved(root, value):
    return font.Font(root, font=value).actual('family')

@pytest.mark.parametrize('theme', ['sticker', 'retro'])
def test_family_is_global_and_does_not_shrink_controls(ui, theme):
    w, root = ui
    w.set_theme(theme)
    initial = resolved(root, w.editor.cget('font'))
    choices = [f for f in w.available_fonts if resolved(root, (f, 11)) != initial]
    assert choices, 'Verification requires two distinct resolved font families'
    choice = choices[0]
    w.set_font_family(choice)
    expected = resolved(root, (choice, 11))
    for style in ('Quiet.TButton', 'Brand.TLabel', 'Sticky.Treeview', 'PaperMeta.TLabel'):
        assert resolved(root, w.style.lookup(style, 'font')) == expected, style
    for surface in (w.library_caption, w.more_menu, w.research_menu, w.icon_menu):
        assert resolved(root, surface.cget('font')) == expected
    w.open_appearance()
    assert resolved(root, w.appearance.font_box.cget('font')) == expected
    before = w.style.lookup('Quiet.TButton', 'font')
    w.set_text_size(25)
    assert w.style.lookup('Quiet.TButton', 'font') == before


def test_plain_text_and_metric_relative_wrapped_leading(ui):
    w, root = ui
    assert not w.editor.tag_ranges('title')
    assert not w.editor.tag_ranges('heading')
    assert not w.editor.tag_ranges('code')
    for zoom in (25, 100, 200):
        w.set_text_size(zoom)
        metrics = font.Font(root, font=w.editor.cget('font')).metrics('linespace')
        assert int(w.editor.cget('spacing2')) >= round(metrics * .3)
        assert w.editor.get('1.0', '1.end') == 'Ordinary first line'


def test_font_change_preserves_draft_caret_and_window_size(ui):
    w, root = ui
    w.editor.insert('end', '\nUnsaved draft')
    w.editor.mark_set('insert', '1.4')
    before = w.editor.get('1.0', 'end-1c')
    geometry = root.geometry()
    w.set_font_family(w.available_fonts[-1])
    assert w.editor.get('1.0', 'end-1c') == before
    assert w.editor.index('insert') == '1.4'
    assert root.geometry() == geometry


def test_hud_prioritises_note_and_keeps_secondary_actions_in_menu(ui):
    w, root = ui
    w.set_presentation('hud'); root.update()
    assert not w.capture.winfo_ismapped()
    assert not w.skin_caption.winfo_ismapped()
    assert not w.buttons['research'].winfo_ismapped()
    labels = [w.more_menu.entrycget(i, 'label') for i in range(w.more_menu.index('end') + 1) if w.more_menu.type(i) not in ('separator', 'tearoff')]
    assert 'Research with Hermes' in labels
    assert 'Mark done' in labels
    assert 'Pin or unpin note' in labels
    pin_index = next(i for i in range(w.more_menu.index('end') + 1) if w.more_menu.type(i) == 'command' and w.more_menu.entrycget(i, 'label') == 'Pin or unpin note')
    w.more_menu.invoke(pin_index)
    assert w.store.get(1).status == 'pinned'
    assert w.editor.winfo_ismapped()
    w.set_presentation('window'); root.update()
    if not w.library.winfo_ismapped():
        w.buttons['library'].invoke(); root.update()
    assert w.capture.winfo_ismapped()
    if not w.paper.winfo_ismapped():
        w.buttons['library'].invoke(); root.update()
    assert w.buttons['research'].winfo_ismapped()


def test_interface_scale_is_independent_and_survives_reopen(ui):
    w, root = ui
    before = font.Font(root, font=w.style.lookup('Quiet.TButton', 'font')).metrics('linespace')
    body = w.editor.cget('font')
    w.set_interface_size(150)
    assert font.Font(root, font=w.style.lookup('Quiet.TButton', 'font')).metrics('linespace') > before
    assert w.editor.cget('font') == body
    w.set_text_size(25)
    assert w.interface_size == 150
    w.close()
    other_root = tk.Tk(); other = Widget(other_root, w.store)
    try:
        assert other.interface_size == 150
    finally: other.close()


def test_unchanged_zoom_does_not_reenter_typography(ui, monkeypatch):
    w, root = ui
    calls = []
    monkeypatch.setattr(w, '_apply_typography', lambda: calls.append(True))
    w.set_text_size(w.text_size)
    assert calls == [], 'A Scale callback for the current value must be a no-op'
    w.set_interface_size(w.interface_size)
    assert calls == []


@pytest.mark.parametrize('mode', ['window', 'hud'])
def test_large_interface_keeps_close_and_menu_reachable(ui, mode):
    w, root = ui
    w.set_presentation(mode)
    w.set_interface_size(200)
    root.update()
    for key in ('more', 'close', 'send', 'copy'):
        b = w.buttons[key]
        x = b.winfo_rootx() - root.winfo_rootx()
        y = b.winfo_rooty() - root.winfo_rooty()
        assert b.winfo_ismapped()
        assert 0 <= x and x + b.winfo_width() <= root.winfo_width(), key
        assert 0 <= y and y + b.winfo_height() <= root.winfo_height(), key


def test_optional_styling_never_changes_plain_note_bytes(ui):
    w, root = ui
    before = w.editor.get('1.0', 'end-1c')
    w.styled_text_var.set(True); w.toggle_styled_text()
    assert w.editor.tag_ranges('title')
    w.styled_text_var.set(False); w.toggle_styled_text()
    assert not w.editor.tag_ranges('title')
    assert w.editor.get('1.0', 'end-1c') == before
