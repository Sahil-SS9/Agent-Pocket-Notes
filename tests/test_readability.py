"""DPI and zoom regressions: use the operator's observed 288-DPI scaling in Xvfb."""
import json
import os
import pytest
from sticky_intent.store import Store
from sticky_intent.widget import Widget, tk, font

pytestmark = pytest.mark.gui


@pytest.fixture
def ui():
    assert os.getenv('DISPLAY'), 'Run only in Xvfb'
    root = tk.Tk(); original = float(root.tk.call('tk', 'scaling'))
    root.tk.call('tk', 'scaling', 4.0)  # 288 dpi / 72 points per inch
    store = Store(); widget = None
    try:
        widget = Widget(root, store); root.update()
        yield widget, store, root
    finally:
        if widget is not None and not widget.closed:
            root.tk.call('tk', 'scaling', original)
            widget.close()
        else:
            # Tk's scaling is display-global, including after this root closes.
            reset = tk.Tk(); reset.withdraw()
            reset.tk.call('tk', 'scaling', original); reset.destroy()


def test_note_and_ui_fonts_scale_with_display_dpi(ui):
    w, s, r = ui
    s.add('Readable at 288 DPI\nReal note text'); w.select(1); r.update()
    body = font.Font(r, font=w.editor.cget('font'))
    assert body.metrics('linespace') >= 40, 'Physical-pixel fonts ignore the desktop scale'
    meta = font.Font(r, font=w.style.lookup('Meta.TLabel', 'font'))
    assert meta.metrics('linespace') >= 30
    assert w.family.casefold() in {x.casefold() for x in font.families(r)}, 'Named Tk fonts are not font families'


def test_dpi_aware_defaults_do_not_leave_controls_outside_window(ui):
    w, s, r = ui
    s.add('A readable note'); w.select(1); r.update()
    assert r.winfo_width() > 700, 'High DPI needs a properly sized content window'
    for key, control in w.buttons.items():
        if not control.winfo_ismapped(): continue
        x = control.winfo_rootx() - r.winfo_rootx(); y = control.winfo_rooty() - r.winfo_rooty()
        assert 0 <= x and x + control.winfo_width() <= r.winfo_width(), key
        assert 0 <= y and y + control.winfo_height() <= r.winfo_height(), key


def test_larger_text_control_preserves_editor_and_survives_reopen(ui):
    w, s, r = ui
    s.add('My exact draft'); w.select(1); w.editor.mark_set('insert', '1.3')
    before = font.Font(r, font=w.editor.cget('font')).metrics('linespace')
    assert callable(getattr(w, 'set_text_size', None)), 'Provide an actual larger-text control'
    w.set_text_size(125); r.update()
    assert font.Font(r, font=w.editor.cget('font')).metrics('linespace') > before
    assert w.editor.get('1.0', 'end-1c') == 'My exact draft' and w.editor.index('insert') == '1.3'
    w.close()
    root = tk.Tk(); root.tk.call('tk', 'scaling', 4.0); reopened = Widget(root, s); root.update()
    try:
        assert reopened.text_size == 125
        assert reopened.selected is not None and reopened.selected.body == 'My exact draft'
    finally: reopened.close()


def test_unsupported_saved_text_size_falls_back(ui):
    w, s, r = ui
    w.close()
    (s.home/'widget-state.json').write_text(json.dumps({'text_size': {'bad': 1}}))
    root = tk.Tk(); root.tk.call('tk', 'scaling', 4.0); other = Widget(root, s)
    try: assert other.text_size == 100
    finally: other.close()


def test_high_dpi_navigation_has_no_font_dependent_symbol_labels(ui):
    w, s, r = ui
    assert str(w.buttons['send'].cget('text')).isascii()
    assert str(w.buttons['collapse'].cget('text')).isascii()
    assert str(w.buttons['more'].cget('text')).isascii()
    assert r.winfo_pixels(w.style.lookup('Slim.Vertical.TScrollbar', 'width')) >= 30


def test_note_preview_does_not_render_hidden_storage_columns(ui):
    w, s, r = ui
    s.add('Readable preview'); w.select(1); r.update()
    assert tuple(w.trees['inbox'].cget('displaycolumns')) == (), 'Storage values must not become a second clipped table'
