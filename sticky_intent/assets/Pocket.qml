import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: win
    objectName: "pocketWindow"
    visible: true
    title: "Pocket Notes · 0.5.0"
    flags: Qt.Window | Qt.FramelessWindowHint
    color: "transparent"
    property string skin: pocket.preferences.theme
    property bool glassTheme: skin === "glass"
    property bool fieldTheme: skin === "field"
    property bool dark: pocket.preferences.dark || skin === "midnight" || (pocket.mode === "capture" && skin === "modern")
    property string family: pocket.preferences.font_family
    property real ui: pocket.preferences.interface_size / 100
    property real reading: pocket.preferences.text_size / 100
    property bool libraryOpen: false
    property bool syncing: false
    property bool viewMenuOpen: false
    property bool historyOpen: false
    property string historyGroup: "recent"
    property int headerCharacterLimit: 48
    property color connectionDot: agents.status.can_run ? "#2ea86b" : agents.checking ? "#d97706" : "#9aa3ad"
    property color ink: dark ? "#edf0f5" : fieldTheme ? "#34392d" : glassTheme ? "#12223c" : "#241e32"
    property color muted: dark ? "#b7c2d3" : fieldTheme ? "#605b49" : glassTheme ? "#4a627a" : "#4f5866"
    property color line: skin === "sticker" ? (dark ? "#c9bbdc" : "#2f2940") : fieldTheme ? (dark ? "#5c6258" : "#cbc3a8") : glassTheme ? (dark ? "#576b84" : "#b9cfdb") : dark ? "#596579" : "#dfe3e8"
    property color chrome: dark ? (glassTheme ? Qt.rgba(0.14,0.2,0.32,0.82) : fieldTheme ? "#30332d" : "#252b36") : glassTheme ? Qt.rgba(0.93,0.975,1,0.76) : fieldTheme ? "#e8dfc8" : skin === "retro" ? "#ece9d8" : skin === "sticker" ? "#f8c6d7" : "#ffffff"
    property color paper: dark ? (glassTheme ? "#202b3c" : fieldTheme ? "#292d28" : "#252b36") : glassTheme ? "#ffffff" : fieldTheme ? "#fff9e9" : skin === "retro" ? "#fffdf3" : skin === "sticker" ? "#fff3a9" : skin === "paper" ? "#fffbef" : "#ffffff"
    property color accent: dark ? "#c4b5fd" : glassTheme ? "#287f99" : fieldTheme ? "#a94f43" : skin === "sticker" ? "#ffce4f" : skin === "retro" ? "#f4d46b" : "#355cd4"
    property color accentInk: dark || skin === "sticker" || skin === "retro" ? "#241e32" : "#ffffff"
    property color actionSheetSurface: glassTheme ? Qt.rgba(0.93,0.97,1,0.84) : fieldTheme ? "#f7f0de" : chrome
    property color actionGroupSurface: dark ? (glassTheme ? "#202b3c" : fieldTheme ? "#30332d" : "#303846") : glassTheme ? "#f1f6fb" : fieldTheme ? "#eee5d0" : skin === "sticker" ? "#fff5c4" : skin === "retro" ? "#f5f1dd" : "#f4f6fb"
    property color actionGroupBorder: dark ? (glassTheme ? "#576b84" : fieldTheme ? "#5c6258" : "#657084") : glassTheme ? "#b9cfdb" : fieldTheme ? "#d1c5a6" : skin === "sticker" ? "#ccaf5b" : skin === "retro" ? "#b9ad75" : "#d7dce8"
    property color actionTitleInk: glassTheme ? "#193b54" : fieldTheme ? "#56372f" : dark ? "#edf0f5" : skin === "sticker" ? "#3f304c" : skin === "retro" ? "#36305f" : "#2e3f76"
    property color actionHeadingInk: dark ? "#edf0f5" : glassTheme ? "#193b54" : fieldTheme ? "#56372f" : skin === "sticker" ? "#3f304c" : skin === "retro" ? "#36305f" : "#2e3f76"
    property color actionDangerInk: dark ? "#ffb4bd" : "#852d39"
    property color hover: dark ? "#3c4960" : glassTheme ? Qt.rgba(1,1,1,0.58) : fieldTheme ? "#e5dcc4" : skin === "sticker" ? "#c9f6dc" : "#e9efff"
    property real corner: skin === "retro" ? 0 : skin === "sticker" || glassTheme ? 22 : fieldTheme ? 5 : 14
    property real pad: skin === "retro" || glassTheme ? 12 : fieldTheme ? 10 : 8
    palette.window: chrome
    palette.windowText: ink
    palette.base: paper
    palette.text: ink
    palette.button: chrome
    palette.buttonText: ink
    palette.highlight: accent
    palette.highlightedText: accentInk
    palette.mid: muted
    palette.dark: muted
    palette.placeholderText: muted
    font.family: family
    font.pixelSize: Math.round(14 * ui)
    onClosing: function(event) { event.accepted = pocket.closeAllowed() }

    function loadEditor() {
        if (editor.text !== pocket.body) { syncing = true; editor.text = pocket.body; syncing = false }
    }
    function loadDraft() {
        if (captureInput.text !== pocket.draft) { syncing = true; captureInput.text = pocket.draft; syncing = false }
    }
    function searchNotes() { pocket.show("notes"); libraryOpen = true; search.forceActiveFocus() }
    function limitedHeaderTitle(value) {
        var source = String(value || "")
        return source.length > headerCharacterLimit ? source.slice(0, headerCharacterLimit - 1) + "…" : source
    }
    function moveFromDrag(mouse, surface) {
        var p = surface.mapToGlobal(mouse.x, mouse.y)
        win.x = p.x - surface.pressOffset.x; win.y = p.y - surface.pressOffset.y
    }
    Connections {
        target: pocket
        function onDocumentLoaded() { win.loadEditor(); sendDialog.close() }
        function onDraftLoaded() { win.loadDraft() }
        function onRequestSend() { sendDialog.open() }
        function onRequestFocus(name) {
            Qt.callLater(function() { if (name === "captureInput") captureInput.forceActiveFocus(); else if (name === "mascot") mascot.forceActiveFocus(); else editor.forceActiveFocus() })
        }
    }
    Connections {
        target: agents
        function onRunAccepted() { sendDialog.close(); researchDialog.close() }
    }
    Component.onCompleted: { loadEditor(); loadDraft(); pocket.attachDocument(editor.textDocument) }

    component Tool: Button {
        id: control
        property bool primary: false
        property string iconName: ""
        property bool iconReady: toolIcon.status === Image.Ready
        property string tip: text
        hoverEnabled: true
        padding: 8 * win.ui
        leftPadding: padding; rightPadding: padding; topPadding: padding; bottomPadding: padding
        implicitHeight: Math.max(34 * win.ui, contentItem.implicitHeight + topPadding + bottomPadding)
        implicitWidth: Math.max(34 * win.ui, (iconName !== "" ? 20 * win.ui : Math.ceil(labelMetrics.width)) + leftPadding + rightPadding + 2)
        TextMetrics { id: labelMetrics; text: control.text; font: control.contentItem.font }
        Accessible.name: tip
        ToolTip.visible: hovered && tip !== ""
        ToolTip.text: tip
        ToolTip.delay: 500
        contentItem: Text {
            textFormat: Text.PlainText
            text: control.iconName === "" ? control.text : ""
            Image {
                id: toolIcon
                objectName: control.objectName + "Icon"
                anchors.centerIn: parent; width: 20 * win.ui; height: width
                visible: control.iconName !== ""
                source: visible ? control.iconName + (win.dark ? "-light.svg" : "-dark.svg") : ""
                sourceSize: Qt.size(Math.round(width * 2), Math.round(height * 2))
                fillMode: Image.PreserveAspectFit
            }
            color: !control.enabled ? win.muted : control.primary ? win.accentInk : win.ink
            font.family: win.family; font.pixelSize: Math.round(14 * win.ui)
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            wrapMode: Text.Wrap
        }
        background: Rectangle {
            color: !control.enabled ? win.paper : control.primary ? win.accent : control.down || control.hovered ? win.hover : win.skin === "retro" || win.fieldTheme ? win.chrome : win.glassTheme ? Qt.rgba(1,1,1,0.26) : "transparent"
            radius: win.skin === "retro" ? 0 : win.skin === "sticker" ? 10 : win.glassTheme ? 12 : win.fieldTheme ? 4 : 7
            border.width: control.activeFocus ? 2 : !control.enabled || win.skin === "retro" || win.glassTheme || win.fieldTheme ? 1 : 0
            border.color: control.activeFocus ? (win.dark ? "#d5c5ff" : "#6550a8") : win.glassTheme ? Qt.rgba(1,1,1,0.82) : win.fieldTheme ? "#bdb39a" : "#79776d"
            Rectangle { visible: win.skin === "retro"; color: control.down ? "#77776d" : "#ffffff"; height: 2; width: parent.width; anchors.top: parent.top }
            Rectangle { visible: win.skin === "retro"; color: control.down ? "#ffffff" : "#79776d"; height: 2; width: parent.width; anchors.bottom: parent.bottom }
        }
    }
    component Rail: ScrollBar {
        id: rail
        // A ScrollBar handed to a ScrollView is not always laid out by Qt. Guard the paint so an
        // unplaced bar can never draw a coloured block over the panel's first row.
        readonly property bool placed: height > 40 * win.ui && height > width
        contentItem: Rectangle { implicitWidth: 8; implicitHeight: 8; radius: 4; color: rail.pressed ? win.ink : win.muted; visible: rail.placed }
        background: Rectangle { color: rail.placed ? win.paper : "transparent"; radius: 4 }
    }
    component Input: TextField {
        id: field
        font.family: win.family; font.pixelSize: Math.round(14 * win.ui)
        color: win.ink; placeholderTextColor: win.muted; padding: 10 * win.ui
        selectByMouse: true
        background: Rectangle { color: win.paper; radius: win.glassTheme ? 12 : win.fieldTheme || win.skin === "retro" ? 3 : 8; border.color: field.activeFocus ? (win.dark ? "#c4b5fd" : "#6550a8") : win.line; border.width: field.activeFocus ? 2 : 1 }
    }
    component SizeSpin: SpinBox {
        // Compact numeric stepper for the size controls. The stock control stretched
        // to the full panel width and dominated the Appearance section.
        id: sizeSpin
        editable: true
        implicitWidth: 88 * win.ui
        implicitHeight: 30 * win.ui
        font.family: win.family; font.pixelSize: 13 * win.ui
        leftPadding: 22 * win.ui; rightPadding: 22 * win.ui
        background: Rectangle {
            color: win.skin === "retro" ? win.chrome : win.paper
            radius: win.skin === "retro" ? 0 : win.skin === "sticker" ? 9 : win.glassTheme ? 11 : win.fieldTheme ? 3 : 6
            border.color: win.line; border.width: 1
        }
        up.indicator: Rectangle {
            objectName: sizeSpin.objectName + "Up"
            x: sizeSpin.width - width; implicitWidth: 22 * win.ui; implicitHeight: sizeSpin.height
            color: up.pressed || up.hovered ? win.hover : "transparent"
            Text { anchors.centerIn: parent; text: "+"; color: win.muted; font.family: win.family; font.pixelSize: 15 * win.ui }
        }
        down.indicator: Rectangle {
            objectName: sizeSpin.objectName + "Down"
            implicitWidth: 22 * win.ui; implicitHeight: sizeSpin.height
            color: down.pressed || down.hovered ? win.hover : "transparent"
            Text { anchors.centerIn: parent; text: "\u2212"; color: win.muted; font.family: win.family; font.pixelSize: 15 * win.ui }
        }
    }
    component SizeSlider: Slider {
        id: sizeSlider
        from: 25; to: 200; stepSize: 1; wheelEnabled: true
        implicitHeight: 22 * win.ui
        background: Rectangle {
            x: sizeSlider.leftPadding; width: sizeSlider.availableWidth; height: 4 * win.ui
            y: sizeSlider.topPadding + sizeSlider.availableHeight / 2 - height / 2
            radius: height / 2; color: win.line
        }
        handle: Rectangle {
            x: sizeSlider.leftPadding + sizeSlider.visualPosition * (sizeSlider.availableWidth - width)
            y: sizeSlider.topPadding + sizeSlider.availableHeight / 2 - height / 2
            implicitWidth: 14 * win.ui; implicitHeight: 14 * win.ui; radius: height / 2
            color: win.skin === "sticker" ? win.paper : win.chrome
            border.color: win.line; border.width: 1
        }
    }
    component Copy: Label {
        textFormat: Text.PlainText
        color: win.ink; font.family: win.family; font.pixelSize: Math.round(14 * win.ui)
        wrapMode: Text.Wrap
    }
    component ResizeHandle: MouseArea {
        property bool resizeLeft: false
        property bool resizeRight: false
        property bool resizeTop: false
        property bool resizeBottom: false
        property point pointerStart
        property point geometryStart
        property size sizeStart
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        z: 100
        onPressed: function(mouse) {
            pointerStart = mapToGlobal(mouse.x, mouse.y)
            geometryStart = Qt.point(win.x, win.y)
            sizeStart = Qt.size(win.width, win.height)
        }
        onPositionChanged: function(mouse) {
            if (!pressed) return
            var pointer = mapToGlobal(mouse.x, mouse.y)
            var nextX = geometryStart.x
            var nextY = geometryStart.y
            var nextWidth = sizeStart.width
            var nextHeight = sizeStart.height
            if (resizeLeft) {
                nextWidth = Math.max(win.minimumWidth, sizeStart.width + pointerStart.x - pointer.x)
                nextX = geometryStart.x + sizeStart.width - nextWidth
            }
            if (resizeRight) nextWidth = Math.max(win.minimumWidth, sizeStart.width + pointer.x - pointerStart.x)
            if (resizeTop) {
                nextHeight = Math.max(win.minimumHeight, sizeStart.height + pointerStart.y - pointer.y)
                nextY = geometryStart.y + sizeStart.height - nextHeight
            }
            if (resizeBottom) nextHeight = Math.max(win.minimumHeight, sizeStart.height + pointer.y - pointerStart.y)
            win.x = nextX; win.y = nextY; win.width = nextWidth; win.height = nextHeight
        }
    }
    component Sheet: Popup {
        id: sheet
        anchors.centerIn: parent
        modal: true; focus: true
        width: Math.min(win.width - 28, 440 * win.ui)
        height: Math.min(win.height - 28, contentItem.implicitHeight + 28)
        padding: 14
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { objectName: sheet.objectName === "notePopup" && win.glassTheme ? "glassActionSurface" : sheet.objectName + "Surface"; color: sheet.objectName === "notePopup" ? win.actionSheetSurface : win.glassTheme ? Qt.rgba(0.93,0.97,1,0.84) : win.fieldTheme ? "#f7f0de" : win.chrome; radius: win.skin === "retro" ? 0 : win.glassTheme ? 20 : win.fieldTheme ? 4 : 14; border.color: sheet.objectName === "notePopup" ? win.actionGroupBorder : win.glassTheme ? Qt.rgba(1,1,1,0.94) : win.fieldTheme ? "#c9bea4" : win.line; border.width: win.skin === "sticker" ? 2 : 1 }
        Overlay.modal: Rectangle { color: "#55000000" }
    }

    // Distinctive outer grammars. Glass uses layered translucent colour beneath opaque note paper.
    Rectangle { anchors.fill: parent; anchors.leftMargin: 5; anchors.topMargin: 5; color: win.skin === "sticker" ? "#2f2940" : win.glassTheme ? "#314976" : win.fieldTheme ? "#425542" : "#1e4944"; radius: win.corner; visible: pocket.mode !== "icon" && win.skin !== "modern" && win.skin !== "midnight" && win.skin !== "paper" }
    Rectangle {
        id: glassBackdrop; objectName: "glassBackdrop"
        anchors.fill: parent; anchors.margins: win.pad
        visible: win.glassTheme && pocket.mode !== "icon"
        radius: win.corner
        gradient: Gradient {
            GradientStop { position: 0; color: win.dark ? "#293b62" : "#6487bd" }
            GradientStop { position: 0.52; color: win.dark ? "#354b66" : "#83bfd0" }
            GradientStop { position: 1; color: win.dark ? "#443958" : "#b6a5cc" }
        }
        border.color: Qt.rgba(1,1,1,0.42); border.width: 1
        Rectangle { width: parent.width * 0.42; height: parent.width * 0.42; x: parent.width * 0.58; y: parent.height * 0.08; radius: width / 2; color: win.dark ? "#324c7a" : "#83d8e6"; opacity: 0.38 }
        Rectangle { width: parent.width * 0.48; height: parent.width * 0.48; x: parent.width * 0.08; y: parent.height * 0.62; radius: width / 2; color: win.dark ? "#55416b" : "#d5bcdf"; opacity: 0.36 }
    }
    Rectangle {
        id: shell; objectName: "windowShell"
        anchors.fill: parent; anchors.margins: win.pad
        color: win.glassTheme ? Qt.rgba(1,1,1,0.20) : win.chrome
        radius: win.corner
        border.color: win.glassTheme ? Qt.rgba(1,1,1,0.7) : win.line
        border.width: win.skin === "sticker" ? 3 : 1
        visible: pocket.mode !== "icon"
        Rectangle { visible: win.skin === "retro"; anchors.fill: parent; anchors.margins: 3; color: "transparent"; border.color: "#ffffff"; border.width: 2 }
    }
    Rectangle {
        visible: win.skin === "sticker" && (pocket.mode === "notes" || pocket.mode === "hud")
        width: 90; height: 20; x: (win.width - width) / 2; y: 2; rotation: -5
        color: "#c9f6dc"; border.color: "#2f2940"; border.width: 2; z: 3
    }

    ColumnLayout {
        id: notesPane; objectName: "notesPane"
        anchors.fill: parent; anchors.margins: win.pad + (win.skin === "sticker" ? 4 : 2)
        spacing: 0
        visible: pocket.mode === "notes" || pocket.mode === "hud"
        Rectangle {
            objectName: "headerSurface"
            Layout.fillWidth: true
            Layout.preferredHeight: Math.max(52 * win.ui, headerControls.implicitHeight + 16)
            color: win.skin === "retro" ? "#382a69" : win.chrome
            radius: win.skin === "retro" ? 0 : win.glassTheme ? 16 : win.fieldTheme ? 5 : 12
            border.color: win.glassTheme ? Qt.rgba(1,1,1,0.72) : win.fieldTheme ? "#c9bea4" : "transparent"
            border.width: win.glassTheme || win.fieldTheme ? 1 : 0
            MouseArea {
                anchors.fill: parent
                property point pressOffset
                onPressed: function(mouse) { pressOffset = Qt.point(mouse.x + x + notesPane.x, mouse.y + y + notesPane.y) }
                onPositionChanged: function(mouse) { if (pressed) win.moveFromDrag(mouse, this) }
            }
            RowLayout {
                id: headerControls
                anchors.fill: parent; anchors.margins: 8; spacing: 4
                Copy { objectName: "noteHeaderTitle"; text: libraryOpen ? "Your notes" : win.historyOpen ? "Agent history" : win.limitedHeaderTitle(pocket.title); color: win.skin === "retro" ? "#ffffff" : win.ink; wrapMode: Text.NoWrap; elide: Text.ElideRight; maximumLineCount: 1; Layout.fillWidth: true; Layout.minimumWidth: 0; visible: win.width > 420 * win.ui; font.weight: Font.DemiBold }
                Tool { objectName: "collectionButton"; text: libraryOpen || win.historyOpen ? "‹" : "▤"; tip: libraryOpen || win.historyOpen ? "Back to note" : "Open collection · Ctrl+F"; padding: 2 * win.ui; onClicked: { if (win.historyOpen) win.historyOpen = false; else libraryOpen = !libraryOpen } }
                Item { Layout.fillWidth: true; visible: win.width <= 420 * win.ui }
                Tool { objectName: "windowMenu"; text: "⚙"; tip: "Settings"; padding: 2 * win.ui; onClicked: settingsScreen.open() }
                Tool { objectName: "viewChangeButton"; text: "⇄"; tip: "Change view"; padding: 2 * win.ui; visible: win.width > 420; onClicked: viewMenu.open() }
                Tool { objectName: "closeWindow"; text: "×"; tip: "Save and quit"; padding: 2 * win.ui; onClicked: win.close() }
            }
        }
        Rectangle { Layout.fillWidth: true; height: win.skin === "sticker" ? 3 : 1; color: win.line; visible: true }

        // Editor remains instantiated across every view/theme; undo and caret survive.
        Item {
            Layout.fillWidth: true; Layout.fillHeight: true
            Rectangle {
                id: notePaperSurface; objectName: "notePaper"
                anchors.fill: parent; color: win.paper
                radius: win.skin === "sticker" ? 16 : win.fieldTheme ? 4 : 0
                border.color: win.glassTheme ? "#ffffff" : win.fieldTheme ? "#d6c9aa" : "transparent"
                border.width: win.glassTheme || win.fieldTheme ? 1 : 0
                Item {
                    objectName: "fieldRuleLayer"; visible: win.fieldTheme
                    anchors.fill: parent; clip: true
                    Repeater {
                        model: win.fieldTheme ? Math.ceil(parent.height / (28 * win.ui)) : 0
                        Rectangle { x: 0; y: (index + 1) * 28 * win.ui; width: parent.width; height: 1; color: win.dark ? "#53604e" : "#c9d1c0"; opacity: 0.62 }
                    }
                }
                Rectangle {
                    objectName: "fieldMarginRule"; visible: win.fieldTheme
                    x: 30 * win.ui; width: 1; anchors.top: parent.top; anchors.bottom: parent.bottom
                    color: win.dark ? "#a46e68" : "#c97869"; opacity: 0.72
                }
            }
            Flickable {
                id: editorScroll
                anchors.fill: parent; anchors.margins: 2
                visible: !win.libraryOpen && !win.historyOpen
                clip: true; contentWidth: width; contentHeight: editor.contentHeight + 40
                boundsBehavior: Flickable.StopAtBounds
                TextArea.flickable: TextArea {
                    id: editor; objectName: "editor"
                    textFormat: TextEdit.PlainText
                    color: win.ink; placeholderText: "A thought, a snippet, a plan…"; placeholderTextColor: win.muted
                    font.family: win.family; font.pixelSize: Math.round(18 * win.reading)
                    wrapMode: TextEdit.Wrap; selectByMouse: true
                    leftPadding: win.fieldTheme ? 42 * win.ui : 24; rightPadding: win.fieldTheme ? 42 * win.ui : 24; topPadding: 22; bottomPadding: 24
                    background: null
                    onTextChanged: if (!win.syncing) pocket.edit(text)
                    Accessible.name: "Note editor"
                }
                ScrollBar.vertical: Rail { }
            }
            Rectangle {
                objectName: "fieldPageTab"; visible: win.fieldTheme && !win.libraryOpen; z: 3
                anchors.right: notePaperSurface.right; anchors.rightMargin: 7 * win.ui
                anchors.top: notePaperSurface.top; anchors.topMargin: 16 * win.ui
                width: 12 * win.ui; height: 58 * win.ui; color: win.dark ? "#586954" : "#71866b"
                Text { objectName: "fieldPageTabLabel"; anchors.centerIn: parent; width: 48 * win.ui; height: 11 * win.ui; rotation: 90; text: "INDEX"; color: "#fff8e9"; font.family: win.family; font.pixelSize: 8 * win.ui; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
            }
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 16
                visible: win.libraryOpen; spacing: 10
                RowLayout {
                    Layout.fillWidth: true
                    Tool { objectName: "sessionHistoryButton"; iconName: "history"; text: ""; tip: "Agent history · notes you sent to a harness"; onClicked: { win.libraryOpen = false; win.historyOpen = true; agents.refreshHistory() } }
                    Input { id: search; objectName: "search"; placeholderText: "Find a note…"; Layout.fillWidth: true; onTextChanged: pocket.filter(text); Keys.onEscapePressed: { text = ""; win.libraryOpen = false; editor.forceActiveFocus() } }
                    Tool { objectName: "newNoteButton"; text: "+"; tip: "New blank note"; onClicked: { if (pocket.newNote()) { win.libraryOpen=false; search.text="" } } }
                }
                Flow {
                    Layout.fillWidth: true; spacing: 4
                    Repeater {
                        model: ["all","inbox","pinned","done"]
                        Tool { required property string modelData; text: modelData.charAt(0).toUpperCase()+modelData.slice(1)+" "+(pocket.counts[modelData] || 0); onClicked: pocket.statusFilter(modelData) }
                    }
                }
                ListView {
                    id: collection; objectName: "collection"
                    Layout.fillWidth: true; Layout.fillHeight: true; model: pocket.notes; spacing: 10; clip: true
                    delegate: ItemDelegate {
                        id: card
                        required property var modelData
                        width: ListView.view.width - (win.skin === "sticker" ? 5 : 0)
                        height: Math.max(98, contentItem.implicitHeight + 24)
                        onClicked: if (pocket.select(modelData.noteId)) win.libraryOpen=false
                        background: Rectangle {
                            color: card.hovered || card.modelData.selected ? win.hover : win.dark ? "#303a48" : win.skin === "sticker" ? (card.modelData.status === "pinned" ? "#c9f6dc" : "#fff3a9") : win.fieldTheme ? "#fbf5e6" : win.paper
                            radius: win.skin === "retro" ? 0 : win.fieldTheme ? 4 : 12
                            border.color: win.line; border.width: win.skin === "sticker" || win.fieldTheme || card.activeFocus ? 2 : 1
                            Rectangle { visible: win.skin === "sticker"; z: -1; x: 3; y: 3; width: parent.width; height: parent.height; radius: 12; color: "#2f2940" }
                        }
                        contentItem: Column {
                            spacing: 6
                            Copy { width: parent.width; text: card.modelData.title; wrapMode: Text.Wrap; font.weight: Font.DemiBold }
                            Copy { width: parent.width; text: card.modelData.preview; color: win.muted; wrapMode: Text.Wrap }
                            Copy { text: card.modelData.status + (card.modelData.research === "none" ? "" : " · Research " + card.modelData.research); color: win.muted; font.pixelSize: Math.round(12 * win.ui) }
                        }
                    }
                    ScrollBar.vertical: Rail { }
                    Copy { text: "No matching notes. Create one with +."; anchors.centerIn: parent; visible: collection.count === 0; width: parent.width - 20; horizontalAlignment: Text.AlignHCenter }
                }
            }
            ColumnLayout {
                objectName: "historyScreen"; visible: win.historyOpen; spacing: 8
                anchors.fill: parent; anchors.margins: 16
                RowLayout { Layout.fillWidth: true; spacing: 6
                    Copy { objectName: "historyTitle"; text: "Agent history"; font.weight: Font.DemiBold; Layout.fillWidth: true; Layout.minimumWidth: 0; wrapMode: Text.NoWrap; elide: Text.ElideRight; maximumLineCount: 1 }
                    Tool { objectName: "historyRecent"; text: "Recent"; primary: win.historyGroup === "recent"; onClicked: win.historyGroup = "recent" }
                    Tool { objectName: "historyByHarness"; text: "By harness"; primary: win.historyGroup === "byharness"; onClicked: win.historyGroup = "byharness" }
                }
                Copy { objectName: "historyHint"; text: "Notes you sent to a harness, newest activity first. Jump back into a note, or continue its conversation where that harness still has the session."; color: win.muted; font.pixelSize: Math.round(12 * win.ui); Layout.fillWidth: true; Layout.preferredWidth: 0; wrapMode: Text.Wrap }
                Copy { objectName: "historyEmpty"; text: "No agent activity yet. Send or research a note and it appears here."; color: win.muted; Layout.fillWidth: true; Layout.preferredWidth: 0; wrapMode: Text.Wrap; visible: agents.noteHistory.length === 0 }
                ListView {
                    id: historyList; objectName: "historyList"
                    Layout.fillWidth: true; Layout.fillHeight: true
                    clip: true; spacing: 8
                    // One model for both modes: "By harness" arrives as flat header/note rows.
                    model: win.historyGroup === "recent" ? agents.noteHistory : agents.noteHistoryGroupRows
                    delegate: ItemDelegate {
                        id: historyRow
                        required property var modelData
                        width: ListView.view.width
                        height: historyRow.modelData.is_header ? Math.max(28, contentItem.implicitHeight + 8) : Math.max(96, contentItem.implicitHeight + 24)
                        onClicked: if (!historyRow.modelData.is_header) { pocket.select(historyRow.modelData.note_id); win.historyOpen = false }
                        background: Rectangle {
                            visible: !historyRow.modelData.is_header
                            color: historyRow.hovered ? win.hover : win.dark ? "#303a48" : win.skin === "sticker" ? "#fff3a9" : win.fieldTheme ? "#fbf5e6" : win.paper
                            radius: win.skin === "retro" ? 0 : win.fieldTheme ? 4 : 12
                            border.color: win.line; border.width: win.skin === "sticker" || win.fieldTheme || historyRow.activeFocus ? 2 : 1
                            Rectangle { visible: win.skin === "sticker"; z: -1; x: 3; y: 3; width: parent.width; height: parent.height; radius: 12; color: "#2f2940" }
                        }
                        contentItem: Column {
                            id: historyRowText
                            spacing: 6
                            Copy {
                                visible: historyRow.modelData.is_header; width: parent.width
                                text: historyRow.modelData.is_header ? historyRow.modelData.label : ""
                                font.weight: Font.DemiBold
                                Rectangle { visible: parent.visible; anchors.bottom: parent.bottom; width: parent.width; height: 1.5; color: win.ink; opacity: 0.6 }
                            }
                            Copy { visible: !historyRow.modelData.is_header; width: parent.width; text: historyRow.modelData.is_header ? "" : historyRow.modelData.title; wrapMode: Text.Wrap; font.weight: Font.DemiBold }
                            Copy { visible: !historyRow.modelData.is_header; width: parent.width; text: historyRow.modelData.is_header ? "" : historyRow.modelData.preview; color: win.muted; wrapMode: Text.Wrap }
                            Flow {
                                visible: !historyRow.modelData.is_header; width: parent.width; spacing: 4
                                Repeater {
                                    model: historyRow.modelData.is_header ? [] : historyRow.modelData.harness_labels
                                    delegate: Rectangle {
                                        required property string modelData
                                        radius: win.skin === "retro" ? 0 : 6; color: win.hover; border.color: win.line; border.width: 1
                                        implicitWidth: historyChipLabel.implicitWidth + 14; implicitHeight: 20 * win.ui
                                        Text { id: historyChipLabel; anchors.centerIn: parent; text: modelData; color: win.ink; font.family: win.family; font.pixelSize: Math.round(12 * win.ui) }
                                    }
                                }
                            }
                            RowLayout {
                                visible: !historyRow.modelData.is_header; width: parent.width; spacing: 8
                                Copy { text: historyRow.modelData.is_header ? "" : (historyRow.modelData.session_id ? "Session " + historyRow.modelData.session_id.substring(0, 18) : "No session id recorded"); color: win.muted; font.pixelSize: Math.round(12 * win.ui) }
                                Item { Layout.fillWidth: true }
                                Copy { text: historyRow.modelData.is_header ? "" : (historyRow.modelData.replied ? "Replied" : "Sent") + " · " + historyRow.modelData.last_state; color: win.muted; font.pixelSize: Math.round(12 * win.ui) }
                            }
                            RowLayout {
                                visible: !historyRow.modelData.is_header; width: parent.width; spacing: 6
                                Tool { objectName: "historyOpen" + historyRow.modelData.note_id; text: "Open note"; onClicked: { pocket.select(historyRow.modelData.note_id); win.historyOpen = false } }
                                Tool {
                                    objectName: "historyContinue" + historyRow.modelData.note_id
                                    text: (historyRow.modelData.resumable ? "Continue in " : "New run in ") + historyRow.modelData.label
                                    enabled: !historyRow.modelData.is_header && historyRow.modelData.harnesses.length > 0
                                    onClicked: if (!agents.continueWith(historyRow.modelData.note_id, historyRow.modelData.kind, historyRow.modelData.resumable ? historyRow.modelData.session_id : "")) { win.historyOpen = false; sendDialog.open() }
                                }
                            }
                        }
                    }
                }
            }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: win.line; visible: true }
        ColumnLayout {
            visible: !win.libraryOpen; Layout.fillWidth: true; Layout.margins: 10; spacing: 6
            RowLayout {
                Layout.fillWidth: true
                Tool { objectName: "pinButton"; iconName: pocket.noteStatus === "pinned" ? "pin-off" : "pin"; text: pocket.noteStatus === "pinned" ? "Unpin" : "Pin"; tip: text + " note"; enabled: pocket.hasNote; onClicked: pocket.togglePin(); visible: pocket.mode !== "hud" && win.width >= 420 * win.ui }
                Tool { objectName: "copyButton"; iconName: "copy"; text: "Copy"; tip: "Copy note text"; enabled: pocket.hasNote; onClicked: pocket.copy(); visible: pocket.mode !== "hud" && win.width >= 400 * win.ui }
                Tool { objectName: "trashButton"; iconName: "trash-2"; text: "Trash"; tip: "Move note to trash…"; enabled: pocket.hasNote; onClicked: deleteDialog.open(); visible: pocket.mode !== "hud" && win.width >= 430 * win.ui }
                Item { Layout.fillWidth: true }
                Tool { objectName: "sendButton"; text: "Send"; primary: true; enabled: pocket.hasNote; onClicked: pocket.openSend() }
                Tool { text: "Research"; enabled: pocket.hasNote; onClicked: researchDialog.open(); visible: pocket.mode !== "hud" && win.width >= 450 * win.ui }
                Tool { objectName: "noteActions"; text: "···"; tip: "Note actions"; onClicked: notePopup.open() }
            }
            Copy { objectName: "noteStatus"; Layout.fillWidth: true; text: pocket.error || agents.statusText || (pocket.researchState !== "none" ? "Research " + pocket.researchState + " · " : "") + pocket.message; color: pocket.error ? (win.dark ? "#ffb5b5" : "#953744") : win.muted; font.pixelSize: Math.round(12 * win.ui) }
            RowLayout {
                visible: pocket.conflict
                Tool { text: "Keep both"; tip: "Save local draft as a new note"; onClicked: pocket.keepBoth() }
                Tool { text: "Reload…"; tip: "Discard local draft after confirmation"; onClicked: reloadDialog.open() }
            }
        }
    }

    // A toolbar, not a modal note card. It grows only for multiple draft lines/errors.
    ColumnLayout {
        anchors.fill: parent; anchors.margins: win.pad + 10
        visible: pocket.mode === "capture"; spacing: 3
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 6
            Image {
                source: "pocket-note-mascot-alpha.png"; Layout.preferredWidth: 28; Layout.preferredHeight: 28; fillMode: Image.PreserveAspectFit
                MouseArea {
                    anchors.fill: parent; cursorShape: Qt.SizeAllCursor
                    property point start; property point origin
                    onPressed: function(mouse) { start=mapToGlobal(mouse.x,mouse.y); origin=Qt.point(win.x,win.y) }
                    onPositionChanged: function(mouse) { if (pressed) { var p=mapToGlobal(mouse.x,mouse.y); win.x=origin.x+p.x-start.x; win.y=origin.y+p.y-start.y } }
                }
            }
            Flickable {
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                contentWidth: width; contentHeight: captureInput.contentHeight + 12
                TextArea.flickable: TextArea {
                    id: captureInput; objectName: "captureInput"
                    placeholderText: "Capture a thought…"; placeholderTextColor: win.muted
                    color: win.ink; textFormat: TextEdit.PlainText
                    font.family: win.family; font.pixelSize: Math.round(16 * win.ui)
                    wrapMode: TextEdit.Wrap; selectByMouse: true; padding: 8
                    background: Rectangle { visible: win.glassTheme || win.fieldTheme; color: win.paper; radius: win.glassTheme ? 10 : 3; border.color: win.line; border.width: 1 }
                    onTextChanged: if (!win.syncing) pocket.editDraft(text)
                    Keys.onPressed: function(event) { if ((event.modifiers & (Qt.ControlModifier | Qt.MetaModifier)) && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) { pocket.captureSave(); event.accepted = true } }
                    Accessible.name: "Quick capture draft"
                }
                ScrollBar.vertical: Rail { }
            }
            Tool { objectName: "captureSave"; text: "↑"; primary: true; tip: "Save new note · Ctrl+Enter"; onClicked: pocket.captureSave() }
            Tool { objectName: "captureNotes"; text: "▤"; tip: "Open existing notes"; onClicked: pocket.show("notes") }
            Tool { objectName: "captureMinimise"; text: "−"; tip: "Minimise with draft preserved"; onClicked: pocket.show("icon") }
        }
        Copy { objectName: "captureStatus"; text: pocket.error || "Ctrl+Enter saves · minimise keeps your draft"; color: pocket.error ? (win.dark ? "#ffb5b5" : "#953744") : win.muted; Layout.fillWidth: true; font.pixelSize: Math.round(12 * win.ui) }
    }
    Image {
        id: mascot; objectName: "mascot"; anchors.fill: parent; anchors.margins: 4
        visible: pocket.mode === "icon"; source: "pocket-note-mascot-alpha.png"; fillMode: Image.PreserveAspectFit
        activeFocusOnTab: true
        Accessible.name: "Sticky Intent floating icon. Double-click or Enter to restore."
        Keys.onReturnPressed: pocket.restore()
        Keys.onSpacePressed: pocket.restore()
        Keys.onEscapePressed: pocket.raiseNotes()
        MouseArea {
            id: iconMouse; anchors.fill: parent; acceptedButtons: Qt.LeftButton | Qt.RightButton; hoverEnabled: true
            property point start
            property point origin
            property bool moved: false
            onPressed: function(mouse) { start = mapToGlobal(mouse.x,mouse.y); origin=Qt.point(win.x,win.y); moved=false }
            onPositionChanged: function(mouse) {
                if (pressed && pressedButtons & Qt.LeftButton) {
                    var now=mapToGlobal(mouse.x,mouse.y); var dx=now.x-start.x; var dy=now.y-start.y
                    if (Math.abs(dx)+Math.abs(dy)>5) moved=true
                    if (moved) { win.x=origin.x+dx; win.y=origin.y+dy }
                }
            }
            onDoubleClicked: if (!moved) pocket.restore()
            onClicked: function(mouse) { if (mouse.button === Qt.RightButton) { pocket.raiseNotes(); settingsScreen.open() } }
        }
    }


    // Eight resize hit-zones keep resizing separate from note controls.
    ResizeHandle { objectName: "resizeLeft"; visible: pocket.mode !== "icon"; width: 6; height: parent.height - 24; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; resizeLeft: true; cursorShape: Qt.SizeHorCursor }
    ResizeHandle { objectName: "resizeRight"; visible: pocket.mode !== "icon"; width: 6; height: parent.height - 24; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; resizeRight: true; cursorShape: Qt.SizeHorCursor }
    ResizeHandle { objectName: "resizeTop"; visible: pocket.mode !== "icon"; width: parent.width - 24; height: 6; anchors.top: parent.top; anchors.horizontalCenter: parent.horizontalCenter; resizeTop: true; cursorShape: Qt.SizeVerCursor }
    ResizeHandle { objectName: "resizeBottom"; visible: pocket.mode !== "icon"; width: parent.width - 24; height: 6; anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter; resizeBottom: true; cursorShape: Qt.SizeVerCursor }
    ResizeHandle { objectName: "resizeTopLeft"; visible: pocket.mode !== "icon"; width: 12; height: 12; anchors.top: parent.top; anchors.left: parent.left; resizeLeft: true; resizeTop: true; cursorShape: Qt.SizeFDiagCursor }
    ResizeHandle { objectName: "resizeTopRight"; visible: pocket.mode !== "icon"; width: 12; height: 12; anchors.top: parent.top; anchors.right: parent.right; resizeRight: true; resizeTop: true; cursorShape: Qt.SizeBDiagCursor }
    ResizeHandle { objectName: "resizeBottomLeft"; visible: pocket.mode !== "icon"; width: 12; height: 12; anchors.bottom: parent.bottom; anchors.left: parent.left; resizeLeft: true; resizeBottom: true; cursorShape: Qt.SizeBDiagCursor }
    ResizeHandle { objectName: "resizeBottomRight"; visible: pocket.mode !== "icon"; width: 12; height: 12; anchors.bottom: parent.bottom; anchors.right: parent.right; resizeRight: true; resizeBottom: true; cursorShape: Qt.SizeFDiagCursor }
    Popup {
        id: viewMenu; objectName: "viewMenu"; x: win.width - width - 70; y: 48
        modal: true; focus: true; padding: 10
        width: Math.min(win.width - 24, 260); closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: win.glassTheme ? Qt.rgba(0.93,0.97,1,0.84) : win.fieldTheme ? "#f7f0de" : win.chrome; radius: win.glassTheme ? 18 : win.fieldTheme ? 4 : win.corner; border.color: win.glassTheme ? Qt.rgba(1,1,1,0.94) : win.fieldTheme ? "#c9bea4" : win.line; border.width: 1 }
        ColumnLayout { width: viewMenu.availableWidth; spacing: 4
            Copy { objectName: "viewMenuHeading"; text: "Change view"; font.weight: Font.DemiBold }
            Tool { objectName: "viewCapture"; text: "Quick capture"; Layout.fillWidth: true; primary: pocket.mode === "capture"; onClicked: { pocket.show("capture"); viewMenu.close() } }
            Tool { objectName: "viewHud"; text: "HUD"; Layout.fillWidth: true; primary: pocket.mode === "hud"; onClicked: { win.libraryOpen=false; pocket.show("hud"); viewMenu.close() } }
            Tool { objectName: "viewIcon"; text: "Floating icon"; Layout.fillWidth: true; primary: pocket.mode === "icon"; onClicked: { pocket.show("icon"); viewMenu.close() } }
        }
    }
    Sheet {
        id: settingsScreen; objectName: "settingsScreen"
        contentItem: ScrollView { clip: true
            ColumnLayout { width: settingsScreen.availableWidth; spacing: 8
                Copy { objectName: "settingsTitle"; text: "Settings"; font.weight: Font.DemiBold; font.pixelSize: 18 * win.ui }
                Tool { objectName: "settingsViewButton"; text: "Change view…"; Layout.fillWidth: true; visible: win.width <= 420 * win.ui; onClicked: { settingsScreen.close(); viewMenu.open() } }

                Copy { objectName: "settingsAppearanceHeader"; text: "Appearance"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                Rectangle { Layout.fillWidth: true; height: 1; color: win.line }
                Copy { text: "Theme"; color: win.muted; Layout.fillWidth: true }
                Flow { objectName: "themeOptions"; Layout.fillWidth: true; spacing: 4
                    Repeater {
                        model: ["modern","sticker","retro","paper","midnight","glass","field"]
                        Tool {
                            required property string modelData
                            objectName: "theme" + modelData.charAt(0).toUpperCase() + modelData.slice(1)
                            text: modelData === "glass" ? "Liquid Glass" : modelData === "field" ? "Field Journal" : modelData
                            tip: text + " appearance"
                            primary: pocket.preferences.theme === modelData
                            onClicked: pocket.preference("theme",modelData)
                        }
                    }
                }
                Copy { objectName: "selectedThemeLabel"; text: "Current look: " + (pocket.preferences.theme === "glass" ? "Liquid Glass" : pocket.preferences.theme === "field" ? "Field Journal" : pocket.preferences.theme.charAt(0).toUpperCase() + pocket.preferences.theme.slice(1)); color: win.muted; Layout.fillWidth: true }
                CheckBox { objectName: "darkAppearance"; text: "Dark appearance"; checked: pocket.preferences.dark; onToggled: pocket.preference("dark",checked); font.family: win.family; font.pixelSize: 14 * win.ui }
                Copy { text: "Font throughout the app"; Layout.fillWidth: true }
                ComboBox { objectName: "fontFamily"; model: pocket.families; Layout.fillWidth: true; font.family: win.family; font.pixelSize: 14 * win.ui; currentIndex: model.indexOf(win.family); onActivated: pocket.preference("font_family",currentText) }
                ColumnLayout { Layout.fillWidth: true; spacing: 4
                    RowLayout { Layout.fillWidth: true; spacing: 8
                        Copy { objectName: "readingTextLabel"; text: "Reading text"; Layout.fillWidth: true }
                        SizeSpin { objectName: "readingSpin"; from: 25; to: 200; value: pocket.preferences.text_size; Layout.alignment: Qt.AlignVCenter; onValueModified: pocket.sizePreference("text_size",value) }
                        Copy { text: "%"; color: win.muted }
                    }
                    SizeSlider {
                        id: readingSlider; objectName: "readingSlider"; Layout.fillWidth: true
                        onMoved: pocket.sizePreference("text_size",Math.round(value))
                        Binding { target: readingSlider; property: "value"; value: pocket.preferences.text_size; when: !readingSlider.pressed }
                    }
                }
                ColumnLayout { Layout.fillWidth: true; spacing: 4
                    RowLayout { Layout.fillWidth: true; spacing: 8
                        Copy { objectName: "interfaceSizeLabel"; text: "Interface size"; Layout.fillWidth: true }
                        SizeSpin { objectName: "interfaceSpin"; from: 25; to: 200; value: pocket.preferences.interface_size; Layout.alignment: Qt.AlignVCenter; onValueModified: pocket.sizePreference("interface_size",value) }
                        Copy { text: "%"; color: win.muted }
                    }
                    SizeSlider {
                        id: interfaceSlider; objectName: "interfaceSlider"; Layout.fillWidth: true
                        onMoved: if (!pressed) pocket.sizePreference("interface_size",Math.round(value))
                        onPressedChanged: if (!pressed) pocket.sizePreference("interface_size",Math.round(value))
                        Binding { target: interfaceSlider; property: "value"; value: pocket.preferences.interface_size; when: !interfaceSlider.pressed }
                    }
                }
                CheckBox { objectName: "styledText"; text: "Styled headings and code"; checked: pocket.preferences.styled_text; onToggled: pocket.preference("styled_text",checked); font.family: win.family; font.pixelSize: 14 * win.ui }
                Tool { objectName: "resetTextSizes"; text: "Reset text sizes"; Layout.fillWidth: true; onClicked: { pocket.preference("text_size",100); pocket.preference("interface_size",100) } }

                Rectangle { Layout.fillWidth: true; height: 1; color: win.line }
                Copy { objectName: "settingsProviderHeader"; text: "Provider Settings"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                RowLayout { objectName: "providerStatusRow"; Layout.fillWidth: true; Layout.preferredWidth: 0; spacing: 8
                    Item {
                        objectName: "providerStatusIndicatorSlot"
                        Layout.minimumWidth: 24 * win.ui; Layout.preferredWidth: 24 * win.ui; Layout.maximumWidth: 24 * win.ui
                        Layout.preferredHeight: 18 * win.ui
                        Layout.alignment: Qt.AlignTop
                        Rectangle {
                            objectName: "providerStatusDot"
                            width: 10 * win.ui; height: width; anchors.centerIn: parent
                            radius: width / 2; color: win.connectionDot; border.color: win.line; border.width: 1
                            Accessible.name: agents.status.can_run ? "Provider connected" : agents.checking ? "Checking provider connection" : "Provider not connected"
                        }
                    }
                    Copy { objectName: "providerStatus"; text: agents.status.state + " · " + agents.status.reason; color: win.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.minimumWidth: 0 }
                }
                Tool { objectName: "checkProvider"; text: "Check provider connection"; Layout.fillWidth: true; enabled: !agents.checking; onClicked: agents.check() }
                Tool { objectName: "configureHarnesses"; text: "Configure harnesses and models…"; Layout.fillWidth: true; onClicked: { settingsScreen.close(); sessionSetupSource="send"; harnessSetup.open() } }

                Rectangle { Layout.fillWidth: true; height: 1; color: win.line }
                Copy { objectName: "settingsWindowHeader"; text: "Window"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                Tool { objectName: "keepOnTop"; text: pocket.preferences.on_top ? "Stop keeping window on top" : "Keep window on top"; Layout.fillWidth: true; onClicked: pocket.preference("on_top",!pocket.preferences.on_top) }
                Tool { objectName: "resetWindowSize"; text: "Reset window size"; Layout.fillWidth: true; onClicked: pocket.resetWindow() }
                Tool { objectName: "saveAndQuit"; text: "Save and quit"; Layout.fillWidth: true; onClicked: win.close() }
                Tool { objectName: "closeSettings"; text: "Close"; Layout.fillWidth: true; onClicked: settingsScreen.close() }
            }
        }
    }
    Sheet {
        id: notePopup; objectName: "notePopup"
        contentItem: ScrollView {
            clip: true
            ColumnLayout {
                width: notePopup.availableWidth; spacing: 7
                Copy { objectName: "noteActionsTitle"; text: "Note actions"; color: win.actionTitleInk; font.weight: Font.DemiBold }
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: actionGroupCreateContent.implicitHeight + 14; radius: win.glassTheme ? 12 : win.fieldTheme ? 3 : 8
                    color: win.actionGroupSurface
                    border.color: win.actionGroupBorder
                    border.width: 1
                    ColumnLayout { id: actionGroupCreateContent; anchors.fill: parent; anchors.margins: 7; spacing: 3
                        Copy { objectName: "actionGroupCreate"; text: win.fieldTheme ? "I · CREATE & CAPTURE" : "01 · CREATE & CAPTURE"; color: win.actionHeadingInk; font.weight: Font.DemiBold; font.pixelSize: 11 * win.ui }
                        Tool { objectName: "actionNewBlankNote"; text: "New blank note · Ctrl+N"; Layout.fillWidth: true; onClicked: { notePopup.close(); pocket.newNote(); win.libraryOpen=false } }
                        Tool { objectName: "actionCaptureClipboard"; text: "Capture clipboard · Ctrl+Shift+V"; Layout.fillWidth: true; onClicked: { notePopup.close(); pocket.pasteCapture() } }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: actionGroupOrganiseContent.implicitHeight + 14; radius: win.glassTheme ? 12 : win.fieldTheme ? 3 : 8
                    color: win.actionGroupSurface
                    border.color: win.actionGroupBorder
                    border.width: 1
                    ColumnLayout { id: actionGroupOrganiseContent; anchors.fill: parent; anchors.margins: 7; spacing: 3
                        Copy { objectName: "actionGroupOrganise"; text: win.fieldTheme ? "II · ORGANISE" : "02 · ORGANISE"; color: win.actionHeadingInk; font.weight: Font.DemiBold; font.pixelSize: 11 * win.ui }
                        Tool { objectName: "actionPin"; text: pocket.noteStatus === "pinned" ? "Unpin note" : "Pin note"; enabled: pocket.hasNote; Layout.fillWidth: true; onClicked: pocket.togglePin() }
                        Tool { objectName: "actionDone"; text: pocket.noteStatus === "done" ? "Restore to inbox" : "Mark done"; enabled: pocket.hasNote; Layout.fillWidth: true; onClicked: pocket.mark(pocket.noteStatus === "done" ? "inbox" : "done") }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: actionGroupShareContent.implicitHeight + 14; radius: win.glassTheme ? 12 : win.fieldTheme ? 3 : 8
                    color: win.actionGroupSurface
                    border.color: win.actionGroupBorder
                    border.width: 1
                    ColumnLayout { id: actionGroupShareContent; anchors.fill: parent; anchors.margins: 7; spacing: 3
                        Copy { objectName: "actionGroupShare"; text: win.fieldTheme ? "III · SHARE" : "03 · SHARE"; color: win.actionHeadingInk; font.weight: Font.DemiBold; font.pixelSize: 11 * win.ui }
                        Tool { objectName: "actionCopy"; text: "Copy text"; enabled: pocket.hasNote; Layout.fillWidth: true; onClicked: pocket.copy() }
                        Tool { objectName: "actionSend"; text: "Send…"; enabled: pocket.hasNote; Layout.fillWidth: true; onClicked: { notePopup.close(); pocket.openSend() } }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: actionGroupHermesContent.implicitHeight + 14; radius: win.glassTheme ? 12 : win.fieldTheme ? 3 : 8
                    color: win.actionGroupSurface
                    border.color: win.actionGroupBorder
                    border.width: 1
                    ColumnLayout { id: actionGroupHermesContent; anchors.fill: parent; anchors.margins: 7; spacing: 3
                        Copy { objectName: "actionGroupHermes"; text: win.fieldTheme ? "IV · HERMES" : "04 · HERMES"; color: win.actionHeadingInk; font.weight: Font.DemiBold; font.pixelSize: 11 * win.ui }
                        Tool { objectName: "actionResearch"; text: "Research…"; enabled: pocket.hasNote; Layout.fillWidth: true; onClicked: { notePopup.close(); researchDialog.open() } }
                        Tool { objectName: "actionResearchLogs"; text: "Research logs…"; enabled: pocket.logs.length > 0; Layout.fillWidth: true; onClicked: { notePopup.close(); logDialog.open() } }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: actionGroupDangerContent.implicitHeight + 14; radius: win.glassTheme ? 12 : win.fieldTheme ? 3 : 8
                    color: win.actionGroupSurface
                    border.color: win.actionGroupBorder
                    border.width: 1
                    ColumnLayout { id: actionGroupDangerContent; anchors.fill: parent; anchors.margins: 7; spacing: 3
                        Copy { objectName: "actionGroupDanger"; text: win.fieldTheme ? "V · DANGER" : "05 · DANGER"; color: win.actionDangerInk; font.weight: Font.DemiBold; font.pixelSize: 11 * win.ui }
                        Tool { objectName: "actionTrash"; text: "Move to trash…"; enabled: pocket.hasNote; Layout.fillWidth: true; onClicked: { notePopup.close(); deleteDialog.open() } }
                    }
                }
                Tool { objectName: "backFromNoteActions"; text: "Back"; Layout.fillWidth: true; onClicked: notePopup.close() }
            }
        }
    }
    component HarnessSheet: Sheet {
        id: harnessSheet
        property string operation: "send"
        onOpened: agents.begin(operation)
        contentItem: ScrollView {
            clip: true
            ColumnLayout {
                width: harnessSheet.availableWidth; spacing: 8
                Copy { text: harnessSheet.operation === "research" ? "Research with an agent" : "Send to an agent"; font.weight: Font.DemiBold }
                // Harness chips — O3 locked: two taps to launch, hover highlight everywhere.
                // preferredWidth 0 keeps a long chip row wrapping inside the panel instead of
                // inflating the scroll content and adding a sideways bar.
                Flow {
                    objectName: harnessSheet.operation + "HarnessChips"; Layout.fillWidth: true; Layout.preferredWidth: 0; spacing: 6
                    Repeater {
                        model: agents.harnesses
                        Tool { required property var modelData; text: modelData.label; enabled: !agents.checking; onClicked: agents.choose(modelData.kind); Component.onCompleted: objectName = harnessSheet.operation + "HarnessChip" }
                    }
                }
                Copy { objectName: harnessSheet.operation + "HarnessStatus"; text: agents.status.state + " · " + agents.status.reason; Layout.fillWidth: true; Layout.preferredWidth: 0; color: win.muted; wrapMode: Text.Wrap }
                Tool { objectName: harnessSheet.operation + "StartNewRun"; text: harnessSheet.operation === "research" ? "Start new research run" : "Start new run"; primary: true; Layout.fillWidth: true; enabled: !agents.checking && !agents.running && agents.status.can_run && pocket.hasNote && pocket.body.trim().length > 0; onClicked: agents.startNew() }
                // A) locked waiting feedback (ticket-stub banner)
                Rectangle {
                    objectName: harnessSheet.operation + "WaitingBanner"; visible: agents.running || agents.checking
                    Layout.fillWidth: true; radius: 10; color: "transparent"; border.color: "#d97706"; border.width: 2
                    height: waitText.implicitHeight + 18
                    ColumnLayout { id: waitCol; anchors.centerIn: parent; spacing: 2
                        Copy { id: waitText; text: agents.running ? "Agent working — reply lands under your text" : "Checking the connection…"; color: "#d97706"; font.weight: Font.DemiBold }
                    }
                }
                // B) locked error card: note never edited, retry offered
                Rectangle {
                    objectName: harnessSheet.operation + "ErrorCard"; visible: !agents.running && agents.runJobs.length > 0 && agents.runJobs[0].state === "failed"
                    Layout.fillWidth: true; radius: 10; color: "#fdeef1"; border.color: "#c2384f"; border.width: 1.5
                    ColumnLayout { anchors.fill: parent; anchors.margins: 10; spacing: 4
                        Copy { text: "Run failed — your note was not changed."; color: "#c2384f"; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.Wrap }
                        Copy { text: agents.runJobs.length ? agents.runJobs[0].error : ""; color: "#c2384f"; Layout.fillWidth: true; wrapMode: Text.Wrap }
                        Tool { text: "Retry"; Layout.fillWidth: true; enabled: agents.status.can_run; onClicked: agents.startNew() }
                    }
                }
                // Sessions grouped per harness (locked O3) with underlined mini-titles
                Repeater {
                    model: agents.harnesses
                    delegate: ColumnLayout {
                        required property var modelData
                        property string harnessKind: modelData.kind
                        readonly property var groupSessions: agents.sessions.filter(function(s){ return s.kind === modelData.kind })
                        Layout.fillWidth: true; visible: groupSessions.length > 0; spacing: 6
                        Copy { text: modelData.label + " sessions"; font.weight: Font.DemiBold; Layout.fillWidth: true; Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1.5; color: win.ink; opacity: 0.6 } }
                        Repeater {
                            model: parent.groupSessions
                            Tool {
                                required property var modelData
                                text: modelData.label
                                Layout.fillWidth: true
                                enabled: !agents.checking && modelData.enabled && (modelData.mode === "context" ? harnessSheet.operation === "send" : agents.status.can_run && agents.status.can_resume)
                                onClicked: modelData.mode === "context" ? agents.attachContext(modelData.token) : agents.startSession(modelData.token)
                            }
                        }
                    }
                }
                Copy { text: "No sessions yet for this harness. Start a new run and it appears here."; visible: agents.sessions.length === 0; color: win.muted; Layout.fillWidth: true; Layout.preferredWidth: 0; wrapMode: Text.Wrap }
                Item { Layout.fillWidth: true; height: 4 }
                RowLayout { objectName: harnessSheet.operation + "FooterControls"; Layout.fillWidth: true; spacing: 8
                    Tool { objectName: harnessSheet.operation + "CheckHarness"; text: agents.checking ? "Checking…" : "Recheck connection"; enabled: !agents.checking; Layout.fillWidth: true; onClicked: agents.check() }
                    Tool { text: "Set-up…"; objectName: harnessSheet.operation + "HarnessOptions"; Layout.fillWidth: true; onClicked: { sessionSetupSource = harnessSheet.operation; harnessSheet.close(); harnessSetup.open() } }
                }
                Tool {
                    id: cancelHarnessButton
                    objectName: harnessSheet.operation + "Cancel"; text: "Cancel"; Layout.fillWidth: true
                    onClicked: harnessSheet.close()
                    background: Rectangle {
                        objectName: harnessSheet.operation + "CancelBackground"
                        color: cancelHarnessButton.down || cancelHarnessButton.hovered ? win.hover : win.chrome
                        radius: win.skin === "retro" ? 0 : win.skin === "sticker" ? 10 : win.glassTheme ? 12 : win.fieldTheme ? 4 : 7
                        border.color: win.line; border.width: 1
                    }
                }
            }
        }
    }
    property string sessionSetupSource: "send"
    HarnessSheet { id: sendDialog; objectName: "sendDialog"; operation: "send" }
    HarnessSheet { id: researchDialog; objectName: "researchDialog"; operation: "research" }
    Sheet {
        id: harnessSetup; objectName: "harnessOptions"
        property bool advanced: false
        onOpened: {
            var o=agents.configuration
            harnessExecutable.text=o.executable || agents.selected; harnessModel.text=o.model || ""
            harnessProvider.text=o.provider || ""; harnessProfile.text=o.profile || ""
            harnessHome.text=o.home || ""; harnessCwd.text=o.cwd || ""
        }
        contentItem: ScrollView {
            clip: true
            ColumnLayout {
                width: harnessSetup.availableWidth; spacing: 6
                RowLayout { objectName: "harnessSetupHeader"; Layout.fillWidth: true; spacing: 6
                    Tool {
                        objectName: "harnessSetupBack"; text: "← Back"; tip: "Back to " + (sessionSetupSource === "research" ? "research" : "send")
                        onClicked: { harnessSetup.close(); if (sessionSetupSource === "research") researchDialog.open(); else sendDialog.open() }
                    }
                    Copy {
                        objectName: "harnessSetupTitle"
                        text: (sessionSetupSource === "research" ? "Research" : "Send") + " set-up · " + agents.selected
                        font.weight: Font.DemiBold; wrapMode: Text.NoWrap; elide: Text.ElideRight; maximumLineCount: 1
                        Layout.fillWidth: true; Layout.minimumWidth: 0
                    }
                }
                // S2 locked checklist: see everything, touch nothing you don't need.
                RowLayout { Layout.fillWidth: true; spacing: 8
                    Item {
                        objectName: "setupConnectionIndicatorSlot"
                        Layout.minimumWidth: 24 * win.ui; Layout.preferredWidth: 24 * win.ui; Layout.maximumWidth: 24 * win.ui
                        Layout.preferredHeight: 18 * win.ui
                        Layout.alignment: Qt.AlignTop
                        Rectangle {
                            objectName: "setupConnectionDot"
                            width: 10 * win.ui; height: width; anchors.centerIn: parent
                            radius: width / 2; color: win.connectionDot; border.color: win.line; border.width: 1
                            Accessible.name: agents.status.can_run ? "Provider connected" : agents.checking ? "Checking provider connection" : "Provider not connected"
                        }
                    }
                    ColumnLayout { Layout.fillWidth: true; spacing: 0
                        Copy { objectName: "setupConnectTitle"; text: "Connect " + agents.selected; font.weight: Font.DemiBold }
                        Copy { text: agents.status.state === "not_installed" ? "not installed yet" : agents.status.state === "ready" ? "ready in your account" : "use the native sign-in flow"; color: win.muted; font.pixelSize: 12*win.ui; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    }
                    Tool { objectName: "setupConnect"; text: agents.status.state === "not_installed" ? "Install" : agents.status.state === "ready" ? "DONE" : "Connect"; enabled: !agents.checking; onClicked: agents.setup() }
                }
                RowLayout { Layout.fillWidth: true; spacing: 8
                    Copy { text: "②"; Layout.preferredWidth: 20 }
                    ColumnLayout { Layout.fillWidth: true; spacing: 0
                        Copy { text: "Pick a model"; font.weight: Font.DemiBold }
                        Copy { text: "uses " + agents.selected + "’s own picker"; color: win.muted; font.pixelSize: 12*win.ui }
                    }
                    Tool { objectName: "setupModelPicker"; text: "OPEN"; enabled: !agents.checking; onClicked: agents.modelPicker() }
                }
                RowLayout { Layout.fillWidth: true; spacing: 8
                    Copy { text: "③"; Layout.preferredWidth: 20 }
                    ColumnLayout { Layout.fillWidth: true; spacing: 0
                        Copy { text: "Test the connection"; font.weight: Font.DemiBold }
                        Copy { objectName: "setupStatusText"; text: agents.statusText !== "" ? agents.statusText : "verifies version, sign-in and model"; color: win.muted; font.pixelSize: 12*win.ui; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    }
                    Tool { objectName: "setupCheck"; text: agents.checking ? "…" : "TEST"; enabled: !agents.checking; onClicked: agents.check() }
                }
                ColumnLayout { Layout.fillWidth: true; visible: harnessSetup.advanced; spacing: 4
                    RowLayout { Layout.fillWidth: true; spacing: 8
                        Copy { text: "④"; Layout.preferredWidth: 20 }
                        Copy { text: "Advanced paths"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                    }
                    Copy { text: "Model override"; Layout.leftMargin: 28; color: win.muted; font.pixelSize: 12*win.ui }
                    Input { id: harnessModel; objectName: "harnessModel"; Layout.fillWidth: true; Layout.leftMargin: 28 }
                    Copy { text: "Provider override (optional)"; visible: agents.selected === "hermes" || agents.selected === "pi"; Layout.leftMargin: 28; color: win.muted; font.pixelSize: 12*win.ui }
                    Input { id: harnessProvider; objectName: "harnessProvider"; visible: agents.selected === "hermes" || agents.selected === "pi"; Layout.fillWidth: true; Layout.leftMargin: 28 }
                    Copy { text: "Harness profile (optional)"; visible: agents.selected === "hermes" || agents.selected === "codex"; Layout.leftMargin: 28; color: win.muted; font.pixelSize: 12*win.ui }
                    Input { id: harnessProfile; objectName: "harnessProfile"; visible: agents.selected === "hermes" || agents.selected === "codex"; Layout.fillWidth: true; Layout.leftMargin: 28 }
                    Copy { text: "Working directory (optional absolute path)"; Layout.leftMargin: 28; color: win.muted; font.pixelSize: 12*win.ui }
                    Input { id: harnessCwd; objectName: "harnessCwd"; Layout.fillWidth: true; Layout.leftMargin: 28 }
                    Copy { text: "Executable override"; Layout.leftMargin: 28; color: win.muted; font.pixelSize: 12*win.ui }
                    Input { id: harnessExecutable; objectName: "harnessExecutable"; Layout.fillWidth: true; Layout.leftMargin: 28 }
                    Copy { text: "Hermes home override"; visible: agents.selected === "hermes"; Layout.leftMargin: 28; color: win.muted; font.pixelSize: 12*win.ui }
                    Input { id: harnessHome; objectName: "harnessHome"; visible: agents.selected === "hermes"; Layout.fillWidth: true; Layout.leftMargin: 28 }
                }
                Tool { objectName: "harnessSetupAdvanced"; text: harnessSetup.advanced ? "Hide advanced paths" : "Advanced paths…"; Layout.fillWidth: true; onClicked: harnessSetup.advanced = !harnessSetup.advanced }
                Tool { objectName: "saveHarnessOptions"; text: "Save options"; primary: true; Layout.fillWidth: true; onClicked: if (agents.saveOptions(harnessExecutable.text,harnessModel.text,harnessProvider.text,harnessProfile.text,harnessHome.text,harnessCwd.text)) { harnessSetup.close(); if (agents.intent === "research") researchDialog.open(); else sendDialog.open() } }
                Tool { objectName: "copySetupCommand"; text: "Copy native setup command"; Layout.fillWidth: true; onClicked: agents.copySetup() }
            }
        }
    }
    Sheet {
        id: deleteDialog; objectName: "deleteDialog"
        contentItem: ColumnLayout {
            Copy { text: "Move this note to trash?"; Layout.fillWidth: true }
            Copy { text: "The Markdown file is kept in the store's trash folder."; Layout.fillWidth: true }
            Tool { text: "Move to trash"; Layout.fillWidth: true; onClicked: { pocket.deleteNote(); deleteDialog.close() } }
            Tool { text: "Cancel"; Layout.fillWidth: true; onClicked: deleteDialog.close() }
        }
    }
    Sheet {
        id: reloadDialog
        contentItem: ColumnLayout {
            Copy { text: "Discard this local draft and reload? Keep both is safer if you want both versions."; Layout.fillWidth: true }
            Tool { text: "Reload from disk"; Layout.fillWidth: true; onClicked: { pocket.reload(); reloadDialog.close() } }
            Tool { text: "Cancel"; Layout.fillWidth: true; onClicked: reloadDialog.close() }
        }
    }
    Sheet {
        id: logDialog
        height: win.height-40
        contentItem: ColumnLayout {
            Copy { text: "Research logs (local files)"; font.weight: Font.DemiBold }
            Repeater { model: pocket.logs; Tool { required property var modelData; text: modelData.runner+" · "+modelData.state; Layout.fillWidth: true; onClicked: logText.text=pocket.readLog(modelData.path) } }
            ScrollView { Layout.fillWidth: true; Layout.fillHeight: true; TextArea { id: logText; text: "Choose a log above."; readOnly: true; wrapMode: TextEdit.Wrap; color: win.ink; font.family: win.family; font.pixelSize: 14*win.ui; background: null } }
            Tool { text: "Close"; Layout.fillWidth: true; onClicked: logDialog.close() }
        }
    }
    Shortcut { sequence: "Ctrl+V"; enabled: !editor.activeFocus && !search.activeFocus && !captureInput.activeFocus; onActivated: pocket.pasteCapture() }
    Shortcut { sequence: "Meta+V"; enabled: !editor.activeFocus && !search.activeFocus && !captureInput.activeFocus; onActivated: pocket.pasteCapture() }
    Shortcut { sequence: "Ctrl+N"; onActivated: { pocket.newNote(); win.libraryOpen=false } }
    Shortcut { sequence: "Ctrl+Shift+V"; onActivated: pocket.pasteCapture() }
    Shortcut { sequence: "Ctrl+F"; onActivated: win.searchNotes() }
    Shortcut { sequence: "Ctrl+L"; onActivated: win.searchNotes() }
    Shortcut { sequence: "Ctrl+S"; onActivated: pocket.save() }
    Shortcut { sequence: "Ctrl+P"; onActivated: pocket.togglePin() }
    Shortcut { sequence: "Ctrl+R"; onActivated: { pocket.show("notes"); researchDialog.open() } }
    Shortcut { sequence: "Ctrl+Return"; enabled: pocket.mode==="notes"; onActivated: pocket.sendLast() }
    Shortcut { sequence: "Meta+N"; onActivated: { pocket.newNote(); win.libraryOpen=false } }
    Shortcut { sequence: "Meta+F"; onActivated: win.searchNotes() }
    Shortcut { sequence: "Meta+P"; onActivated: pocket.togglePin() }
    Shortcut { sequence: "Meta+R"; onActivated: researchDialog.open() }
    Shortcut { sequence: "Meta+Shift+V"; onActivated: pocket.pasteCapture() }
    Shortcut { sequence: "Meta+Return"; enabled: pocket.mode==="notes"; onActivated: pocket.sendLast() }
}
