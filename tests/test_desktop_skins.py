"""Native skins, HUD/icon transitions and available-font/25–200% controls.

All roots/stores belong to the pytest sandbox; run only under Xvfb.
"""
import json
import os
from types import SimpleNamespace

import pytest
from sticky_intent.store import Store
from sticky_intent.widget import Widget, THEMES, tk, font

pytestmark = pytest.mark.gui


@pytest.fixture
def ui():
    assert os.getenv('DISPLAY'), 'Xvfb only'
    root = tk.Tk(); original = float(root.tk.call('tk', 'scaling'))
    root.tk.call('tk', 'scaling', 96 / 72)
    store = Store(); store.add('Keep this draft\nAn actual local note.'); store.add('Another thought')
    w = Widget(root, store); w.select(1); root.update()
    yield w, store, root
    if not w.closed:
        root.tk.call('tk', 'scaling', original); w.close()
    else:
        reset = tk.Tk(); reset.withdraw(); reset.tk.call('tk', 'scaling', original); reset.destroy()


def presentation(w, mode):
    assert callable(getattr(w, 'set_presentation', None)), 'Native window/HUD/icon modes are missing'
    w.set_presentation(mode); w.root.update()


@pytest.mark.parametrize('skin', ['sticker', 'retro'])
def test_two_skins_preserve_real_editor_and_store(ui, skin):
    w, s, r = ui
    assert skin in THEMES, f'The chosen {skin} skin is missing'
    editor = w.editor; w.editor.insert('end-1c', ' edited'); w.editor.mark_set('insert', '2.4'); r.update()
    w.set_theme(skin); r.update()
    assert w.editor is editor and w.editor.index('insert') == '2.4'
    assert w.editor.get('1.0', 'end-1c').endswith(' edited')
    assert w.editor.cget('background') == THEMES[skin]['paper']
    w.save(); assert s.get(1).body.endswith(' edited')


@pytest.mark.parametrize('size', [25, 37, 100, 173, 200])
def test_actual_reading_size_accepts_entire_percentage_range(ui, size):
    w, s, r = ui
    w.set_text_size(size); r.update()
    f = font.Font(r, font=w.editor.cget('font'))
    assert w.text_size == size and w.text_size_var.get() == size
    assert f.actual('size') == max(1, round(13 * size / 100)), 'Do not silently floor reading text at 8pt'
    assert w.editor.get('1.0', 'end-1c') == s.get(1).body
    assert font.Font(r, font=w.style.lookup('Quiet.TButton', 'font')).actual('size') >= 10


@pytest.mark.parametrize('invalid', [24, 201, True, 125.5, '100', None, []])
def test_invalid_size_does_not_change_preference(ui, invalid):
    w, s, r = ui
    with pytest.raises(ValueError): w.set_text_size(invalid)
    assert w.text_size == 100


def test_available_font_picker_really_changes_family_and_preserves_undo(ui):
    w, s, r = ui
    assert callable(getattr(w, 'set_font_family', None)), 'A real available-font picker is missing'
    available = {f.casefold(): f for f in font.families(r)}
    original_family = font.Font(r, font=w.editor.cget('font')).actual('family').casefold()
    # X core font names may be aliases; prove a genuinely different resolved
    # face rather than incorrectly assuming every advertised name is canonical.
    other = next(f for f in available.values()
                 if font.Font(r, family=f, size=13).actual('family').casefold() != original_family)
    resolved = font.Font(r, family=other, size=13).actual('family').casefold()
    w.editor.edit_reset(); w.editor.insert('end-1c', ' change'); w.editor.mark_set('insert', '2.2'); r.update()
    w.set_font_family(other); r.update()
    assert font.Font(r, font=w.editor.cget('font')).actual('family').casefold() == resolved
    assert resolved != original_family
    assert w.editor.index('insert') == '2.2'
    w.editor.edit_undo(); assert w.editor.get('1.0', 'end-1c') == s.get(1).body
    with pytest.raises(ValueError): w.set_font_family('not-a-real-font-family-8123')
    assert w.family.casefold() == other.casefold()


def test_appearance_controls_are_wired_not_just_labels(ui):
    w, s, r = ui
    assert callable(getattr(w, 'open_appearance', None)), 'Appearance needs a native font/size control panel'
    w.open_appearance(); r.update()
    panel = w.appearance
    assert panel.window.winfo_ismapped()
    panel.size_scale.set(25); r.update()
    assert w.text_size == 25 and font.Font(r, font=w.editor.cget('font')).actual('size') <= 4
    panel.size_scale.set(200); r.update()
    assert w.text_size == 200 and font.Font(r, font=w.editor.cget('font')).actual('size') == 26
    panel.font_box.set(w.mono_family); panel.font_box.event_generate('<<ComboboxSelected>>'); r.update()
    assert w.family.casefold() == w.mono_family.casefold()
    w.open_appearance(); assert w.appearance is panel
    panel.close(); assert w.appearance is None


@pytest.mark.parametrize('skin', ['sticker', 'retro'])
def test_hud_is_native_frameless_and_keeps_core_actions(ui, skin):
    w, s, r = ui
    assert w.buttons['focus'].cget('text') == 'HUD'
    assert skin in THEMES, 'Requested native skins missing'
    w.set_theme(skin); editor=w.editor; before=r.geometry()
    presentation(w, 'hud')
    assert w.buttons['focus'].cget('text') == 'Window'
    assert w.presentation == 'hud' and bool(r.overrideredirect())
    assert w.editor is editor and w.editor.winfo_ismapped()
    assert not w.notebook.winfo_ismapped()
    for name in ['send','copy','icon','more','close']:
        assert w.buttons[name].winfo_ismapped(), name
    presentation(w, 'window')
    assert not r.overrideredirect() and w.notebook.winfo_ismapped()
    assert r.geometry() == before


@pytest.mark.parametrize('mode', ['window','hud'])
def test_icon_is_a_real_small_window_and_keyboard_reopens_previous_mode(ui, mode):
    w, s, r = ui
    presentation(w, mode); editor=w.editor; before=r.geometry()
    presentation(w, 'icon')
    assert w.presentation == 'icon' and bool(r.overrideredirect())
    assert r.winfo_width() <= w._px(96) and r.winfo_height() <= w._px(96)
    assert not w.editor.winfo_ismapped() and w.icon_canvas.winfo_ismapped()
    assert w.icon_canvas.bind('<Double-Button-1>'), 'Double-click must open, not only a demo label'
    w.icon_canvas.focus_force(); r.update(); w.icon_canvas.event_generate('<Return>'); r.update()
    assert w.presentation == mode and w.editor is editor and w.editor.winfo_ismapped()
    assert r.geometry() == before


def test_icon_drag_moves_clamps_and_never_opens_on_release(ui):
    w,s,r=ui; presentation(w,'icon'); r.geometry('+100+100');r.update()
    w.icon_canvas.event_generate('<ButtonPress-1>',x=20,y=20,rootx=120,rooty=120)
    w.icon_canvas.event_generate('<B1-Motion>',x=40,y=40,rootx=220,rooty=240)
    w.icon_canvas.event_generate('<ButtonRelease-1>',x=40,y=40,rootx=220,rooty=240);r.update()
    assert (r.winfo_x(),r.winfo_y()) == (200,220)
    assert w.presentation=='icon' and not w.editor.winfo_ismapped()
    w._drag_start(SimpleNamespace(x_root=220,y_root=240))
    w._drag(SimpleNamespace(x_root=99999,y_root=99999));r.update()
    assert r.winfo_x()+r.winfo_width() <= r.winfo_screenwidth()
    assert r.winfo_y()+r.winfo_height() <= r.winfo_screenheight()


def test_double_click_after_drag_does_not_accidentally_open(ui):
    w,s,r=ui;presentation(w,'icon')
    w._drag_start(SimpleNamespace(x_root=100,y_root=100))
    w._drag(SimpleNamespace(x_root=160,y_root=160));r.update()
    w._icon_open_event(SimpleNamespace())
    assert w.presentation=='icon'
    w._drag_start(SimpleNamespace(x_root=160,y_root=160))
    w._icon_open_event(SimpleNamespace())
    assert w.presentation=='window'


def test_drafts_selection_fonts_theme_and_icon_restore_survive_reopen(ui):
    w,s,r=ui
    assert 'retro' in THEMES, 'Skin preference is missing'
    w.set_theme('retro');w.set_text_size(37)
    assert callable(getattr(w,'set_font_family',None)), 'Typography preference missing'
    w.set_font_family(w.mono_family);family=w.family
    w.editor.insert('end-1c',' preserved');r.update()
    presentation(w,'hud');presentation(w,'icon');r.geometry('+180+120');r.update();w.close()
    raw=json.loads((s.home/'widget-state.json').read_text())
    assert raw['presentation']=='icon' and raw['icon_restore']=='hud'
    assert raw['text_size']==37 and raw['font_family']==family
    root=tk.Tk(); reopened=Widget(root,s);root.update()
    try:
        assert reopened.presentation=='icon' and reopened.theme=='retro'
        assert reopened.text_size==37 and reopened.family==family
        reopened.open_from_icon();root.update()
        assert reopened.presentation=='hud' and reopened.selected.id==1
        assert reopened.editor.get('1.0','end-1c').endswith(' preserved')
    finally:reopened.close()


def test_save_failure_refuses_minimise_and_keeps_dirty_editor(ui,monkeypatch):
    w,s,r=ui
    assert callable(getattr(w,'minimize_to_icon',None)), 'No native minimise-to-icon action'
    w.editor.insert('end-1c',' unsaved');r.update()
    def fail(*a,**kw):raise OSError('sandbox disk full')
    with monkeypatch.context() as p:
        p.setattr(s,'update',fail);w.safe(w.minimize_to_icon);r.update()
        assert w.presentation=='window' and w.editor.winfo_ismapped()
        assert w.dirty and 'disk full' in w.status.get()


def test_instance_raise_reopens_icon_instead_of_just_lifting_tiny_window(ui):
    w,s,r=ui;presentation(w,'icon')
    class Instance:
        def poll_raise(self):return True
    w.instance=Instance();w._poll();r.update();w.instance=None
    assert w.presentation=='window' and w.editor.winfo_ismapped()


@pytest.mark.parametrize('skin',['sticker','retro'])
@pytest.mark.parametrize('mode',['window','hud'])
def test_controls_fit_at_25_and_200_percent_in_each_skin_mode(ui,skin,mode):
    w,s,r=ui
    assert skin in THEMES, 'Chosen skin missing'
    w.set_theme(skin);presentation(w,mode)
    for percentage in [25,200]:
        w.set_text_size(percentage);r.update()
        for key,b in w.buttons.items():
            if not b.winfo_ismapped():continue
            x=b.winfo_rootx()-r.winfo_rootx();y=b.winfo_rooty()-r.winfo_rooty()
            assert 0 <= x and x+b.winfo_width() <= r.winfo_width(), (skin,mode,percentage,key)
            assert 0 <= y and y+b.winfo_height() <= r.winfo_height(), (skin,mode,percentage,key)


def test_sticker_skin_has_real_clickable_note_cards_not_a_recoloured_table(ui):
    w,s,r=ui;w.set_theme('sticker');r.update()
    assert hasattr(w,'card_buttons'), 'Sticker Club needs its chosen note-card composition'
    assert w.card_views['inbox'].winfo_ismapped() and not w.trees['inbox'].winfo_ismapped()
    w.card_buttons[2].invoke();r.update()
    assert w.selected.id==2 and w.editor.get('1.0','end-1c')==s.get(2).body
    w.set_theme('retro');r.update()
    assert not w.card_views['inbox'].winfo_ismapped() and w.trees['inbox'].winfo_ismapped()


def test_retro_skin_has_classic_editor_window_chrome(ui):
    w,s,r=ui;w.set_theme('retro');r.update()
    assert hasattr(w,'skin_caption'), 'Retro needs an actual editor window caption'
    assert not w.skin_caption.winfo_ismapped(), 'Decorative caption must not compete with note text'
    assert w.skin_caption.cget('background')=='#382A69'
    assert w.skin_caption.cget('foreground')=='#FFFFFF'
    assert int(w.paper.cget('highlightthickness'))>=3


@pytest.mark.parametrize('skin',['sticker','retro'])
def test_skin_caption_is_not_clipped_at_actual_288dpi(skin):
    r=tk.Tk();original=float(r.tk.call('tk','scaling'));r.tk.call('tk','scaling',4.0)
    w=Widget(r,Store())
    try:
        w.set_theme(skin)
        for mode in ['window','hud']:
            presentation(w,mode);r.geometry('1380x1620+0+0');r.update()
            assert w.brand.winfo_width()>=w.brand.winfo_reqwidth(), (skin,mode,w.brand.winfo_width(),w.brand.winfo_reqwidth())
    finally:
        r.tk.call('tk','scaling',original);w.close()


@pytest.mark.parametrize('skin',['sticker','retro'])
def test_collapsed_skin_header_keeps_reopen_icon_and_menu_reachable(ui,skin):
    w,s,r=ui;w.set_theme(skin);r.geometry('360x520+0+0');r.update()
    w.toggle_collapse();r.update()
    assert not w.buttons['focus'].winfo_ismapped()
    for key in ['collapse','icon','more']:
        b=w.buttons[key]
        assert b.winfo_ismapped()
        assert b.winfo_rooty()-r.winfo_rooty()+b.winfo_height()<=r.winfo_height(), key
    w.buttons['collapse'].invoke();r.update()
    assert w.editor.winfo_ismapped() and r.geometry()=='360x520+0+0'


@pytest.mark.parametrize('skin',['sticker','retro'])
@pytest.mark.parametrize('style',['Quiet.TButton','Secondary.TButton','Primary.TButton','Paper.TButton'])
def test_selected_skin_pressed_controls_keep_visible_text(ui,skin,style):
    w,s,r=ui;w.set_theme(skin)
    def luminance(value):
        rgb=[int(value[i:i+2],16)/255 for i in (1,3,5)]
        linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
        return sum(v*t for v,t in zip(linear,(.2126,.7152,.0722)))
    fg=w.style.lookup(style,'foreground',state=('pressed',))
    bg=w.style.lookup(style,'background',state=('pressed',))
    lo,hi=sorted((luminance(fg),luminance(bg)))
    assert (hi+.05)/(lo+.05)>=4.5,(skin,style,fg,bg)
