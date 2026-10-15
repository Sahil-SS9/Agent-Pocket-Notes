"""Walkthrough regressions through real Qt input and disposable storage."""
import json
import pytest
from test_qt_pocket import qt_ui, named, click

pytestmark = pytest.mark.gui


def by_text(window, text):
    from PySide6.QtCore import QObject
    objects=list(window.findChildren(QObject))
    pending=[window.contentItem()]
    while pending:
        item=pending.pop(); objects.append(item); pending.extend(item.childItems())
    matches = [obj for obj in objects if obj.property('visible') and obj.property('text') == text and obj.property('contentItem') is not None]
    assert matches, text
    return matches[0]


def click_text(window, text):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    button = by_text(window,text)
    QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,button.mapToScene(button.boundingRect().center()).toPoint())
    QTest.qWait(80)


def open_appearance(window):
    from PySide6.QtTest import QTest
    click(window, 'windowMenu')
    QTest.qWait(60)
    return named(window, 'settingsScreen')


def test_icon_artwork_has_no_opaque_checkerboard_border():
    from pathlib import Path
    from PySide6.QtGui import QImage
    from sticky_intent import qt_widget
    im = QImage(str(Path(qt_widget.__file__).with_name('assets')/'pocket-note-mascot-alpha.png'))
    assert im.hasAlphaChannel()
    assert all(im.pixelColor(x,0).alpha()==0 and im.pixelColor(x,im.height()-1).alpha()==0 for x in range(im.width()))
    assert all(im.pixelColor(0,y).alpha()==0 and im.pixelColor(im.width()-1,y).alpha()==0 for y in range(im.height()))


def test_icon_surface_requests_alpha_and_has_no_hover_message(qt_ui):
    from PySide6.QtCore import QObject
    from PySide6.QtTest import QTest
    app,store,engine,bridge,window = qt_ui
    bridge.show('icon'); QTest.qWait(80)
    assert window.format().alphaBufferSize() >= 8
    captured=window.grabWindow()
    assert captured.pixelColor(0,0).alpha()==0
    mascot = named(window,'mascot')
    QTest.mouseMove(window,mascot.mapToScene(mascot.boundingRect().center()).toPoint()); QTest.qWait(650)
    visible_text = [obj.property('text') for surface in app.allWindows() for obj in surface.findChildren(QObject) if obj.property('visible')]
    assert not any(isinstance(text,str) and 'drag to move' in text for text in visible_text)


def test_appearance_drag_wheel_and_both_size_controls(qt_ui):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    app,store,engine,bridge,window = qt_ui
    click(window,'windowMenu'); QTest.qWait(60)
    settings=named(window,'settingsScreen')
    scroll=settings.property('contentItem')
    flick=scroll.property('contentItem')
    for name, key, low in [('readingSlider','text_size',25),('interfaceSlider','interface_size',100)]:
        slider = named(window,name)
        top=slider.mapToScene(QPoint(0,0)).y()
        viewport_top=flick.mapToScene(QPoint(0,0)).y()
        maximum=max(0,flick.property('contentHeight')-flick.property('height'))
        target=max(0,min(maximum,flick.property('contentY')+top-viewport_top-14))
        flick.setProperty('contentY',target)
        QTest.qWait(60)
        point = slider.mapToScene(slider.boundingRect().center()).toPoint()
        left = slider.mapToScene(QPoint(12,int(slider.height()/2))).toPoint()
        right = slider.mapToScene(QPoint(int(slider.width()-12),int(slider.height()/2))).toPoint()
        QTest.mousePress(window,Qt.LeftButton,Qt.NoModifier,left)
        QTest.mouseMove(window,right,50)
        QTest.mouseRelease(window,Qt.LeftButton,Qt.NoModifier,right)
        QTest.qWait(80)
        assert bridge.preferences[key] >= 180
        before = bridge.preferences[key]
        point = slider.mapToScene(slider.boundingRect().center()).toPoint()
        QTest.mouseMove(window,point)
        # QTest.wheelEvent injects a native window-system position (physical
        # pixels); QTest.mouseMove uses logical item coordinates.
        QTest.wheelEvent(window,point*window.devicePixelRatio(),QPoint(0,-120)); QTest.qWait(80)
        assert bridge.preferences[key] < before, (name,slider.property('value'),slider.property('wheelEnabled'),point)
        spin = named(window,'readingSpin' if key=='text_size' else 'interfaceSpin')
        assert spin.property('value') == bridge.preferences[key]
    saved = json.loads(bridge.controller.state_path.read_text())
    assert saved['preferences']['interface_size'] == bridge.preferences['interface_size']


def test_numeric_controls_accept_typed_percentages(qt_ui):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from test_qt_pocket import type_text
    app,store,engine,bridge,window = qt_ui
    open_appearance(window)
    for name,key,value in [('readingSpin','text_size',150),('interfaceSpin','interface_size',125)]:
        spin=named(window,name); entry=spin.property('contentItem'); entry.forceActiveFocus()
        QTest.keyClick(window,Qt.Key_A,Qt.ControlModifier); type_text(window,str(value))
        QTest.keyClick(window,Qt.Key_Return); QTest.qWait(100)
        assert bridge.preferences[key]==value
        slider=named(window,'readingSlider' if key=='text_size' else 'interfaceSlider')
        assert slider.property('value')==value


def test_interface_size_changes_window_and_restores_without_drift(qt_ui):
    from PySide6.QtTest import QTest
    app,store,engine,bridge,window = qt_ui
    original = (window.width(),window.height())
    bridge.preference('interface_size',150); QTest.qWait(80)
    assert window.width() > original[0]
    assert window.height() > original[1]
    bridge.preference('interface_size',100); QTest.qWait(80)
    assert (window.width(),window.height()) == original
    bridge.show('capture')
    capture = (window.width(),window.height())
    bridge.preference('interface_size',125); QTest.qWait(80)
    assert window.width() > capture[0] and window.height() > capture[1]


def test_theme_labels_fit_and_appearance_scroll_reaches_close(qt_ui):
    from PySide6.QtCore import QObject, QPoint, Qt
    from PySide6.QtTest import QTest
    app,store,engine,bridge,window = qt_ui
    popup=open_appearance(window)
    for theme in ['modern','sticker','retro','paper','midnight','Liquid Glass','Field Journal']:
        button=by_text(window,theme); label=button.property('contentItem')
        assert not label.property('truncated')
        assert label.property('lineCount')==1, (theme,label.width(),label.property('contentWidth'))
    # A long dialog must expose its final actions via its real scrollbar.
    scroll=popup.property('contentItem')
    flick=scroll.property('contentItem')
    flick.setProperty('contentY',max(0,flick.property('contentHeight')-flick.property('height')))
    QTest.qWait(100)
    close=by_text(window,'Close'); point=close.mapToScene(close.boundingRect().center()).toPoint()
    assert 0<point.y()<window.height()
    QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,point); QTest.qWait(80)
    assert not popup.property('visible')


def test_research_runner_settings_save_and_setup_command(qt_ui):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from test_qt_pocket import type_text
    app,store,engine,bridge,window=qt_ui
    QTest.keyClick(window,Qt.Key_R,Qt.ControlModifier); QTest.qWait(80)
    click(window,'researchHarnessOptions')
    entry=named(window,'harnessProfile'); entry.forceActiveFocus(); type_text(window,'research')
    entry=named(window,'harnessProvider'); entry.forceActiveFocus(); type_text(window,'openai-codex')
    popup=named(window,'harnessOptions'); flick=popup.property('contentItem').property('contentItem')
    flick.setProperty('contentY',max(0,flick.property('contentHeight')-flick.property('height'))); QTest.qWait(80)
    click(window,'saveHarnessOptions')
    assert bridge.agents.configuration['profile']=='research'
    assert bridge.agents.configuration['provider']=='openai-codex'
    click(window,'researchHarnessOptions'); QTest.qWait(80)
    popup=named(window,'harnessOptions'); flick=popup.property('contentItem').property('contentItem')
    flick.setProperty('contentY',max(0,flick.property('contentHeight')-flick.property('height'))); QTest.qWait(80)
    click(window,'copySetupCommand')
    assert app.clipboard().text()=='hermes --profile research model'
    assert bridge.agents.configuration['profile']=='research'
    assert not (store.home/'research').exists()  # Settings/setup never start a real agent.


def test_menu_long_labels_wrap_instead_of_eliding(qt_ui):
    from PySide6.QtTest import QTest
    app,store,engine,bridge,window = qt_ui
    bridge.preference('interface_size',200)
    window.setWidth(390); window.setHeight(650); QTest.qWait(120)
    click(window,'windowMenu'); QTest.qWait(80)
    click(window,'settingsViewButton'); QTest.qWait(80)
    button=named(window,'viewHud')
    text=button.property('contentItem')
    assert not text.property('truncated')
    assert text.property('lineCount') == 1
