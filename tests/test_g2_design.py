"""Regression coverage for the approved, additive Pocket Notes G2 design."""
import pytest
from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from test_qt_pocket import qt_ui, named, click

pytestmark = pytest.mark.gui


def all_objects(window):
    objects = list(window.findChildren(QObject))
    pending = [window.contentItem()]
    while pending:
        item = pending.pop()
        if not isinstance(item, QQuickItem):
            continue
        objects.append(item)
        pending.extend(item.childItems())
    return objects


def visual_named(window, name):
    matches = [obj for obj in all_objects(window) if obj.objectName() == name]
    assert matches, name
    return matches[0]


def test_glass_and_field_are_additive_valid_preferences(qt_ui):
    app, store, engine, bridge, window = qt_ui
    for theme in ("modern", "sticker", "retro", "paper", "midnight", "glass", "field"):
        assert bridge.preference("theme", theme), theme
        assert bridge.preferences["theme"] == theme


def test_new_theme_choices_are_clickable_and_do_not_replace_existing_options(qt_ui):
    app, store, engine, bridge, window = qt_ui
    click(window, "windowMenu")
    QTest.qWait(80)
    for theme, name in (("glass", "themeGlass"), ("field", "themeField")):
        option = visual_named(window, name)
        position = option.mapToScene(option.boundingRect().center()).toPoint()
        QTest.mouseClick(window, Qt.LeftButton, pos=position)
        QTest.qWait(60)
        assert bridge.preferences["theme"] == theme
        assert window.property("skin") == theme
        assert named(window, "selectedThemeLabel").property("text").endswith("Liquid Glass" if theme == "glass" else "Field Journal")
    for name in ("themeModern", "themeSticker", "themeRetro", "themePaper", "themeMidnight"):
        assert visual_named(window, name).property("visible"), name


def test_g2_opens_one_settings_screen_with_all_existing_purpose_groups(qt_ui):
    app, store, engine, bridge, window = qt_ui
    click(window, "windowMenu")
    QTest.qWait(80)
    assert named(window, "settingsScreen").property("visible")
    assert not any(obj.property("visible") for obj in all_objects(window)
                   if obj.objectName() == "windowPopup")
    for name in ("settingsAppearanceHeader", "settingsProviderHeader", "settingsWindowHeader"):
        assert visual_named(window, name).property("visible"), name
    for name in ("themeModern", "themeSticker", "themeRetro", "themePaper", "themeMidnight", "themeGlass", "themeField"):
        assert visual_named(window, name).property("visible"), name
    for name in ("readingSpin", "readingSlider", "interfaceSpin", "interfaceSlider", "styledText", "resetTextSizes", "keepOnTop", "resetWindowSize", "saveAndQuit"):
        assert visual_named(window, name).property("visible"), name
    for name in ("checkProvider", "configureHarnesses"):
        assert visual_named(window, name).property("visible"), name
    assert not any(obj.objectName() == "fullSessionHistory" for obj in all_objects(window))


def test_settings_screen_scrolls_to_the_preserved_window_controls(qt_ui):
    app, store, engine, bridge, window = qt_ui
    window.setWidth(520)
    window.setHeight(520)
    click(window, "windowMenu")
    QTest.qWait(80)
    settings = named(window, "settingsScreen")
    scroll = settings.property("contentItem")
    flick = scroll.property("contentItem")
    content_height = flick.property("contentHeight")
    viewport_height = flick.property("height")
    assert content_height > viewport_height
    flick.setProperty("contentY", max(0, content_height - viewport_height))
    QTest.qWait(80)
    for name in ("settingsWindowHeader", "keepOnTop", "resetWindowSize", "saveAndQuit", "closeSettings"):
        item = named(window, name)
        assert item.property("visible"), name
        rect = item.mapRectToScene(item.boundingRect())
        assert rect.bottom() <= window.height() + 1, (name, rect)


def test_note_actions_use_grouped_layout_a_without_dropping_commands(qt_ui):
    app, store, engine, bridge, window = qt_ui
    click(window, "noteActions")
    QTest.qWait(80)
    assert named(window, "notePopup").property("visible")
    for name in ("actionGroupCreate", "actionGroupOrganise", "actionGroupShare", "actionGroupHermes", "actionGroupDanger"):
        assert visual_named(window, name).property("visible"), name
    for name in ("actionNewBlankNote", "actionCaptureClipboard", "actionPin", "actionDone", "actionCopy", "actionSend", "actionResearch", "actionResearchLogs", "actionTrash"):
        assert visual_named(window, name).property("visible"), name


def test_note_action_headings_have_contrast_in_every_theme(qt_ui):
    app, store, engine, bridge, window = qt_ui
    themes = ("modern", "sticker", "retro", "paper", "midnight", "glass", "field")
    for theme in themes:
        for dark in (False, True):
            bridge.preference("theme", theme)
            bridge.preference("dark", dark)
            QTest.qWait(30)
            click(window, "noteActions")
            surface = window.property("actionGroupSurface")
            sheet_surface = window.property("actionSheetSurface")
            heading = window.property("actionHeadingInk")
            title_ink = window.property("actionTitleInk")
            danger = window.property("actionDangerInk")
            assert _contrast(heading, surface) >= 4.5, (theme, dark, "section")
            assert _contrast(title_ink, sheet_surface) >= 4.5, (theme, dark, "title")
            assert _contrast(danger, surface) >= 4.5, (theme, dark, "danger")
            assert visual_named(window, "noteActionsTitle").property("color") == title_ink, (theme, dark, "title color")
            for name in ("actionGroupCreate", "actionGroupOrganise", "actionGroupShare", "actionGroupHermes"):
                assert visual_named(window, name).property("color") == heading, (theme, dark, name)
            assert visual_named(window, "actionGroupDanger").property("color") == danger
            click(window, "backFromNoteActions")


def test_interface_size_is_100_by_default_and_ranges_from_25_to_200(qt_ui):
    app, store, engine, bridge, window = qt_ui
    assert bridge.preferences["interface_size"] == 100
    click(window, "windowMenu")
    spin = visual_named(window, "interfaceSpin")
    slider = visual_named(window, "interfaceSlider")
    assert spin.property("from") == 25 and spin.property("to") == 200
    assert slider.property("from") == 25 and slider.property("to") == 200
    assert bridge.preference("interface_size", 25)
    assert bridge.preferences["interface_size"] == 25
    assert bridge.preference("interface_size", 200)
    assert bridge.preferences["interface_size"] == 200
    assert bridge.preference("interface_size", 100)


def _scroll_into_view(window, item, margin=20):
    settings = named(window, "settingsScreen")
    flick = settings.property("contentItem").property("contentItem")
    top = item.mapToScene(QPoint(0, 0)).y()
    viewport_top = flick.mapToScene(QPoint(0, 0)).y()
    maximum = max(0, flick.property("contentHeight") - flick.property("height"))
    flick.setProperty("contentY", max(0, min(maximum, flick.property("contentY") + top - viewport_top - margin)))
    QTest.qWait(80)


def test_appearance_size_controls_are_compact_and_on_one_row(qt_ui):
    """Each size control was three stacked full-width rows; it is now a label row with a
    compact stepper plus one slim slider."""
    app, store, engine, bridge, window = qt_ui
    click(window, "windowMenu")
    QTest.qWait(100)
    ui = window.property("ui")
    panel_width = visual_named(window, "settingsScreen").property("contentItem").property("width")
    for spin_name, label_name, slider_name in (("readingSpin", "readingTextLabel", "readingSlider"),
                                               ("interfaceSpin", "interfaceSizeLabel", "interfaceSlider")):
        spin = visual_named(window, spin_name)
        label = visual_named(window, label_name)
        slider = visual_named(window, slider_name)
        _scroll_into_view(window, spin)
        assert spin.width() <= 100 * ui, (spin_name, spin.width())
        assert spin.height() <= 34 * ui, (spin_name, spin.height())
        assert spin.width() < panel_width / 3, (spin_name, spin.width(), panel_width)
        label_rect = label.mapRectToScene(label.boundingRect())
        spin_rect = spin.mapRectToScene(spin.boundingRect())
        assert label_rect.right() <= spin_rect.left() + 1, (spin_name, label_rect, spin_rect)
        assert label_rect.top() - 2 <= spin_rect.center().y() <= label_rect.bottom() + 2, spin_name
        slider_rect = slider.mapRectToScene(slider.boundingRect())
        assert slider_rect.top() >= spin_rect.bottom() - 1, (slider_name, slider_rect, spin_rect)
        assert slider_rect.width() >= spin_rect.width() * 2, (slider_name, slider_rect, spin_rect)
    assert visual_named(window, "readingSpin").height() == visual_named(window, "interfaceSpin").height()


def test_size_steppers_step_and_respect_their_bounds(qt_ui):
    app, store, engine, bridge, window = qt_ui
    click(window, "windowMenu")
    QTest.qWait(100)
    _scroll_into_view(window, visual_named(window, "readingSpin"))
    bridge.preference("text_size", 100)
    QTest.qWait(120)
    spin = visual_named(window, "readingSpin")
    assert spin.property("value") == 100, spin.property("value")
    click(window, "readingSpinUp")
    assert bridge.preferences["text_size"] == 101, bridge.preferences["text_size"]
    click(window, "readingSpinDown")
    assert bridge.preferences["text_size"] == 100, bridge.preferences["text_size"]
    bridge.preference("text_size", 200)
    QTest.qWait(120)
    assert visual_named(window, "readingSpinUp").property("enabled") is False
    assert visual_named(window, "readingSpinDown").property("enabled") is True
    bridge.preference("text_size", 25)
    QTest.qWait(120)
    assert visual_named(window, "readingSpinDown").property("enabled") is False
    assert visual_named(window, "readingSpinUp").property("enabled") is True
    click(window, "readingSpinUp")
    assert bridge.preferences["text_size"] == 26, bridge.preferences["text_size"]


def test_history_screen_lists_agent_notes_with_harness_label_and_session(qt_ui):
    """The screen lists previous notes, not sessions: each card carries the harness it was
    used with and the session it belongs to, and grouping is by harness."""
    import json
    from pathlib import Path
    from sticky_intent import harnesses as harness_module
    app, store, engine, bridge, window = qt_ui
    note = store.add('Sent to hermes\nPreview line for the card.')
    options = harness_module.options_for(store, 'hermes')
    runs_dir = store.home / 'runs'; runs_dir.mkdir(parents=True, exist_ok=True)
    record = dict(job_id='fixture-history-job', note_id=note.id, kind='hermes', operation='send',
                  requested_session='', session_id='fixture-session-1', title=note.title,
                  options=options, cwd=str(options.get('cwd') or Path.home()), argv=[], input_file='',
                  prompt_sha256='', created='2026-07-01T10:00:00Z', state='done', error='',
                  log='', record=str(runs_dir / 'fixture-history-job.json'))
    (runs_dir / 'fixture-history-job.json').write_text(json.dumps(record))

    click(window, "collectionButton")
    click(window, "sessionHistoryButton")
    QTest.qWait(160)
    screen = visual_named(window, "historyScreen")
    assert screen.property("visible")
    texts = [obj.property("text") for obj in all_objects(window)]
    assert "Sent to hermes" in texts, ([t for t in texts if t and len(str(t)) > 20], len(bridge.agents.noteHistory))
    assert "Hermes" in texts, "the card must be labelled with the harness used"
    assert any(str(text).startswith("Session fixture-session") for text in texts), texts
    continue_button = visual_named(window, "historyContinue" + str(note.id))
    assert continue_button.property("text") == "Continue in Hermes", continue_button.property("text")
    click(window, "historyByHarness")
    QTest.qWait(120)
    grouped = [obj.property("text") for obj in all_objects(window)]
    assert "Hermes · 1 note" in grouped, grouped
    assert "Sent to hermes" in grouped, grouped


def test_header_title_is_capped_before_single_line_elision(qt_ui):
    app, store, engine, bridge, window = qt_ui
    note = store.add("X" * 120 + "\nBody")
    assert bridge.select(note.id)
    title = visual_named(window, "noteHeaderTitle")
    assert title.property("text") == "X" * 47 + "…"
    assert len(title.property("text")) == 48
    assert title.property("lineCount") == 1
    bridge.preference("interface_size", 200)
    QTest.qWait(80)
    assert title.property("lineCount") == 1


def test_session_history_is_only_available_from_notes_search_row(qt_ui):
    app, store, engine, bridge, window = qt_ui
    forbidden = {"fullSessionHistory", "sendSessionHistory", "researchSessionHistory"}
    assert not any(obj.objectName() in forbidden for obj in all_objects(window))
    click(window, "collectionButton")
    history = visual_named(window, "sessionHistoryButton")
    plus = visual_named(window, "newNoteButton")
    search = visual_named(window, "search")
    assert history.property("visible") and plus.property("visible")
    assert history.mapRectToScene(history.boundingRect()).left() < search.mapRectToScene(search.boundingRect()).left()
    assert plus.mapRectToScene(plus.boundingRect()).left() > search.mapRectToScene(search.boundingRect()).left()
    icon = visual_named(window, "sessionHistoryButtonIcon")
    assert icon.property("source").toString().endswith("history-dark.svg")
    assert history.property("iconReady") is True
    # Opening the screen hides the library (and its icon); check the icon while it is on screen.
    click(window, "sessionHistoryButton")
    # The approved mock is a replacement screen, not a modal: no sessionHistory popup may exist.
    assert not any(obj.objectName() == "sessionHistory" for obj in all_objects(window))
    screen = visual_named(window, "historyScreen")
    assert screen.property("visible")
    assert not named(window, "editor").property("visible")
    assert not window.property("libraryOpen")
    assert named(window, "noteHeaderTitle").property("text") == "Agent history"
    assert visual_named(window, "historyRecent").property("primary") is True
    assert visual_named(window, "historyList").property("visible") is True
    click(window, "historyByHarness")
    assert visual_named(window, "historyByHarness").property("primary") is True
    assert visual_named(window, "historyRecent").property("primary") is False
    click(window, "historyRecent")
    assert visual_named(window, "historyRecent").property("primary") is True
    click(window, "collectionButton")
    assert not screen.property("visible")
    assert named(window, "editor").property("visible")
    assert not window.property("libraryOpen")
    click(window, "sendButton")
    assert not any(obj.objectName() in forbidden for obj in all_objects(window))


def test_header_quick_capture_is_removed_and_view_menu_only_has_requested_views(qt_ui):
    app, store, engine, bridge, window = qt_ui
    assert not any(obj.objectName() == "newCapture" for obj in all_objects(window))
    click(window, "viewChangeButton")
    assert not any(obj.objectName() in {"viewNotes", "viewCollapsed"} for obj in all_objects(window))
    for name in ("viewCapture", "viewHud", "viewIcon"):
        assert visual_named(window, name).property("visible")
    click(window, "viewHud")
    assert bridge.mode == "hud"
    assert not window.property("libraryOpen")
    assert visual_named(window, "editor").property("visible")
    assert window.flags() & Qt.WindowStaysOnTopHint
    for name in ("pinButton", "copyButton", "trashButton"):
        assert not visual_named(window, name).property("visible"), name
    assert visual_named(window, "sendButton").property("visible")
    click(window, "noteActions")
    assert visual_named(window, "actionPin").property("visible")
    assert visual_named(window, "actionCopy").property("visible")
    click(window, "backFromNoteActions")


def test_widget_has_edge_and_corner_resize_handles(qt_ui):
    from PySide6.QtCore import QPoint
    app, store, engine, bridge, window = qt_ui
    bridge.show("notes")
    window.setWidth(640)
    window.setHeight(600)
    QTest.qWait(80)
    for name in ("resizeLeft", "resizeRight", "resizeTop", "resizeBottom", "resizeTopLeft", "resizeTopRight", "resizeBottomLeft", "resizeBottomRight"):
        assert visual_named(window, name).property("visible"), name
    def drag_resize(name, delta):
        handle = visual_named(window, name)
        point = handle.mapToScene(handle.boundingRect().center()).toPoint()
        original = (window.width(), window.height(), window.x(), window.y())
        QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.mouseMove(window, point + delta, 50)
        QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, point + delta)
        QTest.qWait(80)
        return original, (window.width(), window.height(), window.x(), window.y())
    original, resized = drag_resize("resizeRight", QPoint(24, 0))
    assert resized[0] >= original[0] + 20
    original, resized = drag_resize("resizeLeft", QPoint(-24, 0))
    assert resized[0] >= original[0] + 20 and resized[2] < original[2]
    original, resized = drag_resize("resizeBottomRight", QPoint(24, 20))
    assert resized[0] >= original[0] + 20 and resized[1] >= original[1] + 16


def test_added_themes_have_distinct_material_and_editor_surfaces(qt_ui):
    app, store, engine, bridge, window = qt_ui
    bridge.preference("theme", "glass")
    QTest.qWait(80)
    click(window, "noteActions")
    glass = named(window, "glassActionSurface")
    paper = named(window, "notePaper")
    assert glass.property("visible")
    assert glass.property("color").alphaF() < 1.0
    assert paper.property("color").alphaF() == 1.0
    bridge.preference("theme", "field")
    QTest.qWait(80)
    assert named(window, "fieldRuleLayer").property("visible")
    assert named(window, "fieldMarginRule").property("visible")
    assert named(window, "fieldPageTab").property("visible")
    assert named(window, "fieldPageTabLabel").property("visible")


def _luminance(color):
    channels = [color.redF(), color.greenF(), color.blueF()]
    linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in channels]
    return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))


def _contrast(first, second):
    low, high = sorted((_luminance(first), _luminance(second)))
    return (high + .05) / (low + .05)


def test_added_themes_keep_normal_and_muted_text_readable_in_light_and_dark(qt_ui):
    app, store, engine, bridge, window = qt_ui
    for theme in ("glass", "field"):
        for dark in (False, True):
            bridge.preference("theme", theme)
            bridge.preference("dark", dark)
            QTest.qWait(40)
            paper = window.property("paper")
            assert _contrast(window.property("ink"), paper) >= 4.5, (theme, dark, "ink")
            assert _contrast(window.property("muted"), paper) >= 4.5, (theme, dark, "muted")


def test_capture_header_keeps_editor_space_without_a_status_dot(qt_ui):
    app, store, engine, bridge, window = qt_ui
    window.setWidth(390)
    window.setHeight(560)
    bridge.preference("interface_size", 200)
    bridge.show("capture")
    QTest.qWait(120)
    editor = named(window, "captureInput")
    assert editor.property("width") >= 80
    assert not any(obj.objectName() == "captureConnectionStatusSlot" for obj in all_objects(window))


def test_view_switcher_routes_capture_hud_icon_without_widget_status_slots(qt_ui):
    app, store, engine, bridge, window = qt_ui
    cases = (("viewCapture", "capture"), ("viewHud", "hud"), ("viewIcon", "icon"))
    for name, mode in cases:
        bridge.show("notes")
        window.setProperty("libraryOpen", False)
        click(window, "viewChangeButton")
        QTest.qWait(60)
        assert named(window, "viewMenu").property("visible")
        click(window, name)
        assert bridge.mode == mode, name
        assert not window.property("libraryOpen"), name
        assert not named(window, "viewMenu").property("visible")
    for mode in ("notes", "hud", "capture", "icon"):
        bridge.show(mode)
        QTest.qWait(60)
        assert not any(obj.objectName() in {
            "connectionStatusSlot", "captureConnectionStatusSlot", "floatingStatusSlot"
        } for obj in all_objects(window)), mode


SHEET_NAMES = ("sendDialog", "researchDialog", "notePopup", "settingsScreen", "harnessOptions")


def _open_panel(window, name):
    """Open a panel and hand back its scroll viewport. Scoped lookups only: wrapping
    every object in the window here is what made the suite flaky."""
    sheet = named(window, name)
    sheet.open()
    QTest.qWait(140)
    return sheet, sheet.property("contentItem")


def _settled(getter, timeout=4.0):
    """Panel content sizing happens during polish; wait for a real measurement."""
    import time
    deadline = time.monotonic() + timeout
    value = getter()
    while not value and time.monotonic() < deadline:
        QTest.qWait(40)
        value = getter()
    return value


def test_scrollable_panels_never_overflow_their_own_width(qt_ui, monkeypatch):
    """A long wrapping label must not inflate the scroll content and add a sideways bar."""
    app, store, engine, bridge, window = qt_ui
    long_reason = ("Agent connections are disabled in local visual-review mode; nothing was run. "
                   "Check the installed harness before starting work. ") * 2
    monkeypatch.setattr("sticky_intent.harnesses.connection",
                        lambda kind, options=None, probe=False: dict(
                            kind=kind, label=kind, state="review_only", can_run=False,
                            can_resume=False, reason=long_reason, executable=""))
    for name in SHEET_NAMES:
        sheet, scroll = _open_panel(window, name)
        column = next(obj for obj in scroll.findChildren(QQuickItem) if obj.parent() is scroll)
        implicit = _settled(lambda: column.implicitWidth())
        assert implicit > 0, (name, "panel content width was never measured")
        assert implicit <= scroll.property("width") + 1, (name, implicit, scroll.property("width"))
        sheet.close()
        QTest.qWait(40)


def test_panels_own_their_scrollbars_and_paint_nothing_over_content(qt_ui):
    """A ScrollBar handed to a ScrollView is left unplaced by Qt and paints a blob over
    the panel's first row, so panels must own theirs."""
    app, store, engine, bridge, window = qt_ui
    for name in SHEET_NAMES:
        sheet, scroll = _open_panel(window, name)
        viewport = scroll.mapRectToScene(scroll.boundingRect())
        for obj in scroll.findChildren(QQuickItem):
            cls = obj.metaObject().className()
            if "ScrollBar" not in cls and cls != "Rail":
                continue
            assert cls != "Rail", (name, "panel must not be handed a custom scrollbar")
            if not obj.isVisible():
                continue
            rect = obj.mapRectToScene(obj.boundingRect())
            spans_edge = rect.height() > viewport.height() / 2 or rect.width() > viewport.width() / 2
            assert not (viewport.contains(rect) and not spans_edge), (name, cls, rect)
        sheet.close()
        QTest.qWait(40)


def test_harness_chips_wrap_inside_the_panel(qt_ui):
    app, store, engine, bridge, window = qt_ui
    for operation in ("send", "research"):
        sheet, scroll = _open_panel(window, operation + "Dialog")
        viewport = scroll.mapRectToScene(scroll.boundingRect())
        chips = scroll.findChild(QObject, operation + "HarnessChips")
        assert chips is not None, operation
        chips_rect = chips.mapRectToScene(chips.boundingRect())
        assert chips_rect.width() <= viewport.width() + 1, (operation, chips_rect, viewport)
        assert chips_rect.right() <= viewport.right() + 1, (operation, chips_rect, viewport)
        sheet.close()
        QTest.qWait(40)


def test_provider_status_dot_and_setup_back_are_in_their_own_layouts(qt_ui, monkeypatch):
    app, store, engine, bridge, window = qt_ui
    monkeypatch.setenv("STICKY_INTENT_REVIEW_MODE", "1")
    connected = dict(bridge.agents._connection)
    connected.update(state="ready", can_run=True, can_resume=True,
                     reason="Authenticated and ready for the selected provider model.")
    bridge.agents._connection = connected
    bridge.agents.changed.emit()
    click(window, "windowMenu")
    settings = visual_named(window, "settingsScreen")
    scroll = settings.property("contentItem")
    flick = scroll.property("contentItem")
    flick.setProperty("contentY", max(0, flick.property("contentHeight") - flick.property("height")))
    QTest.qWait(80)
    status_dot = visual_named(window, "providerStatusDot")
    status_slot = visual_named(window, "providerStatusIndicatorSlot")
    status_text = visual_named(window, "providerStatus")
    assert status_dot.property("visible")
    assert status_dot.property("color").name().lower() == "#2ea86b"
    assert status_slot.width() >= 24 * window.property("ui") - 1
    status_rect = status_dot.mapRectToScene(status_dot.boundingRect())
    status_text_rect = status_text.mapRectToScene(status_text.boundingRect())
    assert status_text_rect.left() - status_rect.right() >= 14 * window.property("ui") - 1
    click(window, "configureHarnesses")
    title = visual_named(window, "harnessSetupTitle")
    back = visual_named(window, "harnessSetupBack")
    setup_dot = visual_named(window, "setupConnectionDot")
    setup_slot = visual_named(window, "setupConnectionIndicatorSlot")
    connect_title = visual_named(window, "setupConnectTitle")
    assert title.property("visible") and back.property("visible") and setup_dot.property("visible")
    assert setup_dot.property("color").name().lower() == "#2ea86b"
    assert setup_slot.width() >= 24 * window.property("ui") - 1
    title_rect = title.mapRectToScene(title.boundingRect())
    back_rect = back.mapRectToScene(back.boundingRect())
    dot_rect = setup_dot.mapRectToScene(setup_dot.boundingRect())
    connect_rect = connect_title.mapRectToScene(connect_title.boundingRect())
    assert back_rect.right() <= title_rect.left() + 1
    assert connect_rect.left() - dot_rect.right() >= 14 * window.property("ui") - 1
    assert not dot_rect.intersects(title_rect)
    assert not any(obj.objectName() == "harnessSetupBackBottom" for obj in all_objects(window))
    click(window, "harnessSetupBack")
    assert visual_named(window, "sendDialog").property("visible")


def test_harness_sheet_setup_and_recheck_share_row_cancel_spans_footer(qt_ui, monkeypatch):
    app, store, engine, bridge, window = qt_ui
    monkeypatch.setenv("STICKY_INTENT_REVIEW_MODE", "1")
    for operation in ("send", "research"):
        sheet = visual_named(window, operation + "Dialog")
        sheet.open()
        QTest.qWait(80)
        flick = sheet.property("contentItem").property("contentItem")
        flick.setProperty("contentY", max(0, flick.property("contentHeight") - flick.property("height")))
        QTest.qWait(80)
        recheck = visual_named(window, operation + "CheckHarness")
        setup = visual_named(window, operation + "HarnessOptions")
        cancel = visual_named(window, operation + "Cancel")
        cancel_background = visual_named(window, operation + "CancelBackground")
        footer = visual_named(window, operation + "FooterControls")
        recheck_rect = recheck.mapRectToScene(recheck.boundingRect())
        setup_rect = setup.mapRectToScene(setup.boundingRect())
        cancel_rect = cancel.mapRectToScene(cancel.boundingRect())
        cancel_background_rect = cancel_background.mapRectToScene(cancel_background.boundingRect())
        footer_rect = footer.mapRectToScene(footer.boundingRect())
        assert abs(recheck_rect.center().y() - setup_rect.center().y()) <= 2
        assert cancel_rect.top() > max(recheck_rect.bottom(), setup_rect.bottom())
        assert cancel_rect.width() >= footer_rect.width() - 1
        assert cancel_background_rect.width() >= footer_rect.width() - 1
        assert cancel_background_rect.height() >= cancel_rect.height() - 1
        assert cancel_background.property("color").alpha() > 0
        click(window, operation + "Cancel")
        assert not sheet.property("visible")
        QTest.qWait(60)
