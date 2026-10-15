"""Real native round-two chooser, icon and theme contracts."""
import pytest
from test_qt_pocket import qt_ui,named,click

pytestmark=pytest.mark.gui


def test_send_starts_with_six_harnesses_not_an_empty_session_dead_end(qt_ui):
    import time
    from PySide6.QtCore import QObject
    from PySide6.QtTest import QTest
    app,store,engine,bridge,window=qt_ui
    bridge.openSend(); QTest.qWait(80)
    flow=named(window,'sendHarnessChips'); chips=flow.childItems()[:6]
    assert len(chips)==6
    start=named(window,'sendStartNewRun')
    assert not start.property('enabled')


def test_research_uses_the_same_harness_flow(qt_ui):
    import time
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    app,store,engine,bridge,window=qt_ui
    QTest.keyClick(window,Qt.Key_R,Qt.ControlModifier); QTest.qWait(80)
    flow=named(window,'researchHarnessChips'); chips=flow.childItems()[:6]
    assert len(chips)==6
    assert named(window,'researchHarnessOptions').property('visible')


@pytest.mark.parametrize('skin',['modern','sticker','retro','paper','midnight','glass','field'])
@pytest.mark.parametrize('dark',[False,True])
def test_native_appearance_text_uses_selected_theme_ink(qt_ui,skin,dark):
    from PySide6.QtTest import QTest
    app,store,engine,bridge,window=qt_ui
    bridge.preference('theme',skin); bridge.preference('dark',dark); QTest.qWait(80)
    click(window,'windowMenu'); QTest.qWait(80)
    spin=named(window,'readingSpin')
    assert spin.property('contentItem').property('color')==window.property('ink')
    def luminance(colour):
        channels=[colour.redF(),colour.greenF(),colour.blueF()]
        linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in channels]
        return sum(v*w for v,w in zip(linear,[.2126,.7152,.0722]))
    def contrast(a,b):
        lo,hi=sorted([luminance(a),luminance(b)]); return (hi+.05)/(lo+.05)
    for surface in ['chrome','paper']:
        assert contrast(window.property('ink'),window.property(surface))>=4.5
        assert contrast(window.property('muted'),window.property(surface))>=4.5
    assert contrast(window.property('accentInk'),window.property('accent'))>=4.5
    from PySide6.QtCore import Qt
    QTest.keyClick(window,Qt.Key_Escape); bridge.openSend(); QTest.qWait(80)
    disabled=named(window,'sendStartNewRun')
    assert not disabled.property('enabled')
    assert contrast(disabled.property('contentItem').property('color'),disabled.property('background').property('color'))>=4.5


def test_copy_pin_trash_use_accessible_real_icons(qt_ui):
    from PySide6.QtTest import QTest
    app,store,engine,bridge,window=qt_ui
    for name,symbol in [('copyButton','copy'),('pinButton','pin'),('trashButton','trash-2')]:
        button=named(window,name)
        assert button.property('iconName')==symbol
        assert button.property('tip')
        image=named(window,name+'Icon')
        assert button.property('iconReady') and image.width()>0  # Qt decoded the real SVG.
    click(window,'copyButton')
    assert app.clipboard().text()==bridge.body
    click(window,'pinButton'); QTest.qWait(80)
    assert bridge.noteStatus=='pinned' and named(window,'pinButton').property('iconName')=='pin-off'
    click(window,'trashButton'); QTest.qWait(80)
    assert named(window,'deleteDialog').property('visible')
    assert store.get(bridge.controller.selected.id).body  # Confirmation has not deleted it.


@pytest.mark.parametrize('kind',['hermes','claude','codex','pi','command-code','opencode'])
def test_native_new_run_returns_reply_for_each_fixture_harness(qt_ui,tmp_path,kind):
    from PySide6.QtCore import QObject,Qt
    from PySide6.QtTest import QTest
    from test_harness_runs import configure
    import time
    app,store,engine,bridge,window=qt_ui
    configure(tmp_path,store,kind)
    bridge.openSend(); QTest.qWait(80)
    target=['hermes','claude','codex','pi','command-code','opencode'].index(kind)
    flow=named(window,'sendHarnessChips')
    chips=[]; deadline=time.monotonic()+2
    while time.monotonic()<deadline and len(flow.childItems())<6:
        QTest.qWait(40)
    chips=flow.childItems()[:6]
    ordered=sorted(chips,key=lambda c:(c.mapToScene(c.boundingRect().topLeft()).y(),c.mapToScene(c.boundingRect().topLeft()).x()))
    target_chip=ordered[target]
    point=target_chip.mapToScene(target_chip.boundingRect().center())
    QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,point.toPoint()); QTest.qWait(80)
    assert bridge.agents.selected==kind
    click(window,'sendCheckHarness')
    deadline=time.monotonic()+8
    while bridge.agents.checking and time.monotonic()<deadline: QTest.qWait(20)
    assert bridge.agents.status['can_run'],bridge.agents.status
    popup=named(window,'sendDialog'); flick=popup.property('contentItem').property('contentItem')
    start=named(window,'sendStartNewRun')
    y=start.mapToScene(start.boundingRect().center()).y()
    flick.setProperty('contentY',max(0,min(flick.property('contentHeight')-flick.property('height'),flick.property('contentY')+y-window.height()/2))); QTest.qWait(80)
    click(window,'sendStartNewRun')
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        if 'FIXTURE ANSWER' in bridge.body and bridge.agents.runJobs and bridge.agents.runJobs[0]['state']=='done': break
        QTest.qWait(40)
    assert 'FIXTURE ANSWER' in bridge.body
    assert bridge.body.startswith('Native sandbox note\nReadable content\n\n## ✉ Reply —')
    assert not popup.property('visible')
    assert len(bridge.agents.runJobs)==1 and bridge.agents.runJobs[0]['state']=='done'


@pytest.mark.parametrize('kind',['hermes','claude','codex','pi','command-code','opencode'])
def test_native_setup_and_model_picker_are_explicit_argv_only_no_note_sent(qt_ui,tmp_path,monkeypatch,kind):
    from test_harness_runs import configure
    from sticky_intent import qt_harnesses
    app,store,engine,bridge,window=qt_ui
    exe=configure(tmp_path,store,kind)
    bridge.agents.choose(kind)
    calls=[]
    monkeypatch.setattr(qt_harnesses.shutil,'which',lambda name:'/fixture/gnome-terminal' if name=='gnome-terminal' else str(exe))
    monkeypatch.setattr(qt_harnesses.subprocess,'Popen',lambda args,**kwargs:calls.append((args,kwargs)))
    original=bridge.body
    bridge.agents.setup(); bridge.agents.modelPicker()
    assert len(calls)==2
    for args,kwargs in calls:
        assert args[:2]==['/fixture/gnome-terminal','--']
        assert str(exe) in args and original not in args
        assert '-q' not in args and '-p' not in args and 'exec' not in args
        assert not kwargs.get('shell',False)
    assert bridge.body==original and bridge.agents.runJobs==[]


