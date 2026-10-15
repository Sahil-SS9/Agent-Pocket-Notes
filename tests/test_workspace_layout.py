"""Owner-approved separated workspace, rather than a recoloured vertical form."""
import pytest
from sticky_intent.store import Store
from sticky_intent.widget import Widget, tk, font

pytestmark = pytest.mark.gui

@pytest.fixture
def ui():
    r=tk.Tk();old=float(r.tk.call('tk','scaling'));r.tk.call('tk','scaling',96/72)
    s=Store();s.add('Read and write here\n\nThe library should not take over the editor.');s.add('Another card\nA useful question')
    w=Widget(r,s);w.select(1);r.update()
    yield w,s,r
    if not w.closed:r.tk.call('tk','scaling',old);w.close()

@pytest.mark.parametrize('skin',['sticker','retro'])
def test_full_window_is_library_left_dominant_editor_right(ui,skin):
    w,s,r=ui;w.set_theme(skin);r.geometry('960x680+0+0');r.update()
    assert w.notebook.winfo_rootx()+w.notebook.winfo_width()<w.paper.winfo_rootx(), 'Library must be LEFT of editor, not stacked above it'
    assert w.paper.winfo_width()>w.notebook.winfo_width()*1.8
    assert w.editor.winfo_height()>r.winfo_height()*.55
    assert abs(w.notebook.winfo_rooty()-w.paper.winfo_rooty())<w._px(180)
    for name in ['new','paste']:
        b=w.buttons[name]
        assert b.winfo_rootx()+b.winfo_width()<w.paper.winfo_rootx(), 'Capture belongs to the library'
    assert w.search_entry.winfo_rootx()+w.search_entry.winfo_width()<w.paper.winfo_rootx()

@pytest.mark.parametrize('skin',['sticker','retro'])
def test_note_actions_are_one_group_inside_editor_region(ui,skin):
    w,s,r=ui;w.set_theme(skin);r.geometry('960x680+0+0');r.update()
    ys=[]
    for name in ['pin','done','copy','send','research']:
        b=w.buttons[name];ys.append(b.winfo_rooty())
        assert w.paper.winfo_rootx()<=b.winfo_rootx()
        assert b.winfo_rootx()+b.winfo_width()<=w.paper.winfo_rootx()+w.paper.winfo_width()
        assert b.winfo_rooty()+b.winfo_height()<=w.paper.winfo_rooty()+w.paper.winfo_height(), 'Agent actions must not be a separate global bar'
    assert max(ys)-min(ys)<w._px(12), 'Desktop actions belong to a single baseline'


def test_new_default_is_a_workspace_not_a_tall_form(ui):
    w,s,r=ui
    assert r.winfo_width()>=850 and r.winfo_height()<=750
    assert w.editor.winfo_height()>400


def test_global_family_updates_navigation_without_changing_reading_scale(ui):
    w,s,r=ui;before=w.style.lookup('Quiet.TButton','font')
    w.set_font_family(w.mono_family);r.update()
    assert w.style.lookup('Quiet.TButton','font')!=before
    assert w.text_size == 100
    assert font.Font(r,font=w.editor.cget('font')).actual('family').casefold()==font.Font(r,family=w.mono_family,size=13).actual('family').casefold()


def test_narrow_window_exposes_library_without_restacking_or_losing_draft(ui):
    w,s,r=ui;r.geometry('420x600+0+0');r.update()
    assert 'library' in w.buttons, 'Narrow windows need an explicit library trigger'
    assert w.buttons['library'].winfo_ismapped() and not w.notebook.winfo_ismapped()
    editor=w.editor;w.editor.insert('end-1c',' unsaved');w.editor.mark_set('insert','3.2');r.update()
    w.buttons['library'].invoke();r.update()
    assert w.notebook.winfo_ismapped()
    w.buttons['library'].invoke();r.update()
    assert w.editor is editor and w.editor.winfo_ismapped()
    assert w.editor.get('1.0','end-1c').endswith(' unsaved') and w.editor.index('insert')=='3.2'


@pytest.mark.parametrize('skin',['sticker','retro'])
def test_hud_is_same_editor_with_grouped_actions_not_a_squeezed_workspace(ui,skin):
    w,s,r=ui;w.set_theme(skin);before=r.geometry();editor=w.editor
    w.set_presentation('hud');r.update()
    assert not w.notebook.winfo_ismapped() and w.editor is editor
    for name in ['copy','send','more','close']:
        assert w.buttons[name].winfo_ismapped()
    for name in ['new','paste','pin','done','research']:
        assert not w.buttons[name].winfo_ismapped()
    assert w.editor.winfo_height()>w._px(180)
    w.set_presentation('window');r.update()
    assert r.geometry()==before and w.notebook.winfo_ismapped()


def test_long_library_can_scroll_and_selected_card_is_reachable(ui):
    w,s,r=ui
    for i in range(35):s.add(f'Note {i}\nBody for {i}')
    w.refresh();r.update()
    assert hasattr(w,'library'), 'Library needs its own bounded pane'
    c=w.card_canvases['inbox'];c.yview_moveto(1);r.update()
    assert c.yview()[0]>0
    w.select(1);r.update()
    b=w.card_buttons[1]
    assert c.winfo_rooty()<=b.winfo_rooty()<c.winfo_rooty()+c.winfo_height()
    c.yview_moveto(0);r.update()
    w.card_buttons[max(w.card_buttons)].event_generate('<Button-5>');r.update()
    assert c.yview()[0]>0, 'Wheel scrolling over a card must scroll its library'


@pytest.mark.parametrize('mode',['window','hud','icon'])
def test_search_shortcut_reveals_real_library_even_from_narrow_or_icon_mode(ui,mode):
    w,s,r=ui;r.geometry('420x600+0+0');r.update()
    w.set_presentation(mode);r.update()
    target=w.icon_canvas if mode=='icon' else w.editor
    target.focus_force();r.update()
    target.event_generate('<Control-f>');r.update()
    assert w.presentation=='window'
    assert w.notebook.winfo_ismapped() and w.search_entry.winfo_ismapped()
    assert r.focus_get()==w.search_entry
