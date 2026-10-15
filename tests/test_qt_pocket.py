"""Real Qt Quick input journeys; no live display, store or agent calls."""
import os
import json
import time
from pathlib import Path
import pytest

pytestmark = pytest.mark.gui


def test_native_factory_available():
    pytest.importorskip('PySide6')
    from sticky_intent import qt_widget
    assert callable(getattr(qt_widget, 'create_window', None)), 'Qt factory must expose the real packaged window for verification'


@pytest.fixture
def qt_ui():
    pytest.importorskip('PySide6')
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtTest import QTest
    from sticky_intent.qt_widget import create_window
    from sticky_intent.store import Store
    from shiboken6 import delete
    app = QGuiApplication.instance() or QGuiApplication([])
    store = Store(); note = store.add('Native sandbox note\nReadable content')
    engine, bridge, window = create_window(app, store)
    window.show(); window.requestActivate(); QTest.qWait(120)
    yield app, store, engine, bridge, window
    bridge.timer.stop(); bridge.poller.stop()
    delete(engine)
    QTest.qWait(20)


def named(window, name):
    from PySide6.QtCore import QObject
    obj = window.findChild(QObject, name)
    assert obj is not None, name
    return obj


def type_text(window, text):
    from PySide6.QtTest import QTest
    for character in text:
        QTest.keyClick(window, character)


def click(window, name):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    obj = named(window, name)
    assert obj.property('visible') and obj.property('enabled'), name
    p = obj.mapToScene(obj.boundingRect().center()).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(60)


def test_native_capture_keyboard_minimise_restore(qt_ui):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    app,s,e,b,w = qt_ui
    original = b.controller.selected.id
    click(w, 'viewChangeButton')
    click(w, 'viewCapture')
    assert b.mode == 'capture'
    draft = named(w,'captureInput'); draft.forceActiveFocus()
    type_text(w, 'Toolbar thought')
    QTest.keyClick(w, Qt.Key_Return)
    type_text(w, 'Second line')
    QTest.qWait(60)
    assert b.draft == 'Toolbar thought\nSecond line'
    click(w,'captureMinimise')
    assert b.mode=='icon'
    QTest.mouseDClick(w, Qt.LeftButton, Qt.NoModifier, named(w,'mascot').mapToScene(named(w,'mascot').boundingRect().center()).toPoint())
    QTest.qWait(80)
    assert b.mode=='capture' and b.draft=='Toolbar thought\nSecond line'
    named(w,'captureInput').forceActiveFocus()
    QTest.keyClick(w,Qt.Key_Return,Qt.ControlModifier); QTest.qWait(80)
    assert b.mode=='icon' and s.list('all')[0].body=='Toolbar thought\nSecond line'
    assert s.get(original).body=='Native sandbox note\nReadable content'


def test_native_edit_caret_undo_and_fonts(qt_ui):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    app,s,e,b,w = qt_ui
    editor = named(w,'editor'); editor.forceActiveFocus(); editor.setProperty('cursorPosition',5)
    type_text(w,'ABC'); QTest.qWait(800)
    assert s.get(b.controller.selected.id).body == 'NativABCe sandbox note\nReadable content'
    caret = editor.property('cursorPosition')
    b.preference('theme','sticker'); b.preference('font_family','Noto Serif')
    QTest.qWait(80)
    assert editor.property('cursorPosition') == caret
    assert editor.property('font').family() == 'Noto Serif'
    QTest.keyClick(w,Qt.Key_Z,Qt.ControlModifier); QTest.qWait(800)
    assert s.get(b.controller.selected.id).body == 'Native sandbox note\nReadable content'
    b.preference('text_size',25); QTest.qWait(50)
    assert editor.property('font').pixelSize() in {4,5}
    b.preference('text_size',200); QTest.qWait(50)
    assert editor.property('font').pixelSize() == 36


def test_native_failure_surface_close_and_conflict(qt_ui,monkeypatch):
    from PySide6.QtTest import QTest
    app,s,e,b,w = qt_ui
    b.show('capture'); b.editDraft('Unsaved exact\n draft')
    monkeypatch.setattr(s,'add',lambda *a,**k: (_ for _ in ()).throw(OSError('Injected disk full')))
    b.captureSave(); QTest.qWait(60)
    assert b.mode=='capture' and b.draft=='Unsaved exact\n draft'
    assert 'disk full' in named(w,'captureStatus').property('text')
    monkeypatch.undo()
    b.show('notes'); b.edit('Local draft')
    s.update(b.controller.selected.id,body='Outside edit')
    assert not b.closeAllowed()
    assert w.isVisible() and b.controller.conflict
    b.keepBoth(); QTest.qWait(50)
    assert b.body=='Local draft'
    assert any(n.body=='Outside edit' for n in s.list('all'))


@pytest.mark.parametrize('theme',['modern','sticker','retro','paper','midnight','glass','field'])
def test_native_theme_controls_fit_at_200_percent(qt_ui,theme):
    from PySide6.QtTest import QTest
    app,s,e,b,w = qt_ui
    b.preference('theme',theme); b.preference('interface_size',200)
    w.setWidth(390); w.setHeight(650); QTest.qWait(120)
    for name in ['windowMenu','closeWindow','collectionButton']:
        obj=named(w,name); rect=obj.mapRectToScene(obj.boundingRect())
        assert rect.left()>=0 and rect.right()<=w.width()+1, (theme,name,rect)
    editor=named(w,'editor')
    assert editor.property('visible') and editor.height()>100
    click(w,'windowMenu')
    assert named(w,'settingsScreen').property('visible')


def test_native_collection_and_send_picker(qt_ui):
    from sticky_intent.targets import Registry, claim_messages
    from PySide6.QtTest import QTest
    app,s,e,b,w = qt_ui
    Registry(s.home).register('claude','fixture-claude',cwd='/synthetic-only')
    click(w,'collectionButton')
    assert w.property('libraryOpen')
    b.filter('Native'); QTest.qWait(60)
    assert len(b.notes)==1
    b.filter(''); w.setProperty('libraryOpen',False)
    b.openSend(); QTest.qWait(100)
    assert named(w,'sendDialog').property('visible')
    assert 'next message' in b.sessions[0]['label']
    # Slot uses the real outbox with an explicitly labelled fixture registry.
    assert b.send('claude','fixture-claude')
    claimed=list(claim_messages(s.home,'claude-fixture-claude'))
    assert len(claimed)==1 and 'Native sandbox note' in claimed[0].message
    claimed[0].ack()
