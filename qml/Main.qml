// SubGrab - downloads and fixes subtitles for your videos
// Copyright (C) 2026 Megatro-nn
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program. If not, see <https://www.gnu.org/licenses/>.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: win
    visible: true
    width: 1240; height: 800
    minimumWidth: 1000; minimumHeight: 640
    title: bridge.appInfo().name
    color: cp.bg
    font.family: "Inter"

    property var cp: bridge.palette
    property string page: "auto"
    property string logoImg: Qt.resolvedUrl("logo.png")

    Connections {
        target: bridge
        function onToast(msg) { toastTxt.text = msg; toast.visible = true; toastTimer.restart() }
        function onPreviewReady(title, text) { previewTitle.text = title; previewText.text = text; previewDlg.open() }
        function onRenamePreviewReady(text, count) { previewTitle.text = "Rename preview (" + count + ")"; previewText.text = text; previewDlg.open() }
    }
    Timer { id: toastTimer; interval: 4000; onTriggered: toast.visible = false }

    // ------------------------------------------------------------ components
    component Card: Rectangle {
        radius: 14
        color: cp.card
        border.color: cp.cardBorder
        border.width: 1
    }
    component Badge: Rectangle {
        property string txt: ""
        property string kind: "ok"
        property int maxW: 10000
        radius: 10; height: 20
        width: Math.min(maxW, Math.max(40, btxt.implicitWidth + 16))
        color: cp[kind + "Soft"]
        visible: txt !== ""
        clip: true
        Text { id: btxt; anchors.centerIn: parent; width: parent.width - 16; text: txt; color: cp[kind]
               font.pixelSize: 11; font.weight: Font.DemiBold; elide: Text.ElideRight; horizontalAlignment: Text.AlignHCenter }
    }
    component NavTab: Rectangle {
        property string icn: ""
        property string txt: ""
        property bool active: false
        signal clicked()
        height: 38; radius: 10
        width: navRow.implicitWidth + 26
        color: active ? cp.accentSoft : (navHov.containsMouse ? cp.input : "transparent")
        Row {
            id: navRow; anchors.centerIn: parent; spacing: 7
            Image { source: bridge.icon(icn, active ? "accent" : "muted"); sourceSize.width: 16; sourceSize.height: 16; width: 16; height: 16 }
            Text { text: txt; color: active ? cp.accent : cp.muted; font.pixelSize: 13
                   font.weight: active ? Font.DemiBold : Font.Normal }
        }
        MouseArea { id: navHov; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: parent.clicked() }
    }
    component Chip: Rectangle {
        id: chipRoot
        property string txt: ""
        property bool on: false
        signal toggled(bool value)
        height: 26; radius: 13
        width: ctxt.implicitWidth + 22
        color: on ? cp.accentSoft : cp.input
        border.color: on ? cp.accent : cp.cardBorder
        Text { id: ctxt; anchors.centerIn: parent; text: chipRoot.txt; font.pixelSize: 12
               color: chipRoot.on ? cp.accent : cp.muted }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: chipRoot.toggled(!chipRoot.on) }
    }
    component MButton: Rectangle {
        id: btnRoot
        property string txt: ""
        property bool primary: false
        property bool enabled2: true
        signal clicked()
        height: 36; radius: 9
        width: Math.max(80, mbtxt.implicitWidth + 28)
        color: !enabled2 ? cp.input : (primary ? cp.accent : cp.input)
        border.color: primary ? "transparent" : cp.cardBorder
        opacity: enabled2 ? 1 : 0.6
        Text { id: mbtxt; anchors.centerIn: parent; text: btnRoot.txt; font.pixelSize: 13
               font.weight: btnRoot.primary ? Font.DemiBold : Font.Normal
               color: btnRoot.primary ? cp.onAccent : cp.fg }
        MouseArea { anchors.fill: parent; enabled: btnRoot.enabled2; cursorShape: Qt.PointingHandCursor; onClicked: btnRoot.clicked() }
    }
    component MInput: Rectangle {
        id: inputRoot
        property alias text: itxt.text
        property string hint: ""
        property string icn: ""
        property bool password: false
        signal accepted()
        signal edited()
        height: 36; radius: 9; color: cp.input; border.color: cp.cardBorder
        Image { visible: inputRoot.icn !== ""; source: inputRoot.icn ? bridge.icon(inputRoot.icn, "muted") : ""
                sourceSize.width: 15; sourceSize.height: 15; x: 11; anchors.verticalCenter: parent.verticalCenter }
        TextInput {
            id: itxt; anchors.fill: parent; leftPadding: inputRoot.icn ? 34 : 12; rightPadding: 10
            verticalAlignment: TextInput.AlignVCenter; color: cp.fg; font.pixelSize: 13
            clip: true; selectByMouse: true; echoMode: inputRoot.password ? TextInput.Password : TextInput.Normal
            onTextChanged: if (!activeFocus) cursorPosition = 0
            onAccepted: inputRoot.accepted()
            onTextEdited: inputRoot.edited()
            Text { visible: !itxt.text && inputRoot.hint; text: inputRoot.hint; color: cp.muted; font.pixelSize: 13
                   x: parent.leftPadding; anchors.verticalCenter: parent.verticalCenter }
        }
    }
    component MCombo: Rectangle {
        id: comboRoot
        property var model: []
        property string current: ""
        signal picked(string value)
        height: 36; radius: 9; color: cp.input; border.color: cp.cardBorder
        width: Math.max(cbtxt.implicitWidth + 44, 130)
        Text { id: cbtxt; x: 12; anchors.verticalCenter: parent.verticalCenter; text: comboRoot.current
               color: cp.fg; font.pixelSize: 13; width: parent.width - 40; elide: Text.ElideRight }
        Text { anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
               text: "\u25BE"; color: cp.muted }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                    onClicked: pop.opened ? pop.close() : pop.open() }
        Popup {
            id: pop
            objectName: "pop"
            y: comboRoot.height + 4
            width: Math.max(comboRoot.width, popCol.implicitWidth + 8)
            height: Math.min(popCol.implicitHeight + 8, 320)
            padding: 4
            background: Rectangle { color: cp.card; border.color: cp.cardBorder; radius: 10 }
            contentItem: Flickable {
                clip: true; contentHeight: popCol.implicitHeight
                Column {
                    id: popCol
                    width: pop.width - 8
                    Repeater {
                        model: comboRoot.model
                        delegate: Rectangle {
                            width: popCol.width; height: 32; radius: 7
                            color: ma.containsMouse ? cp.accentSoft : "transparent"
                            Text { x: 12; anchors.verticalCenter: parent.verticalCenter; text: modelData
                                   color: modelData === comboRoot.current ? cp.accent : cp.fg; font.pixelSize: 13
                                   font.weight: modelData === comboRoot.current ? Font.DemiBold : Font.Normal }
                            MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                        onClicked: { comboRoot.current = modelData; comboRoot.picked(modelData); pop.close() } }
                        }
                    }
                }
            }
        }
    }

    component Check: Rectangle {
        id: chkRoot
        property string txt: ""
        property bool on: false
        signal toggled(bool value)
        height: 24; width: cbx.width + ctx.implicitWidth + 10
        color: "transparent"
        Rectangle { id: cbx; width: 18; height: 18; radius: 5; anchors.verticalCenter: parent.verticalCenter
                    color: chkRoot.on ? cp.accent : cp.input; border.color: chkRoot.on ? cp.accent : cp.cardBorder
            Text { anchors.centerIn: parent; text: "✓"; color: cp.onAccent; font.pixelSize: 12; visible: chkRoot.on } }
        Text { id: ctx; x: cbx.width + 8; anchors.verticalCenter: parent.verticalCenter; text: chkRoot.txt; color: cp.fg; font.pixelSize: 12 }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: chkRoot.toggled(!chkRoot.on) }
    }

    // -------------------------------------------------------------- top bar
    Rectangle {
        id: topbar; width: parent.width; height: 58; color: cp.rail
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: cp.cardBorder }
        Image { source: win.logoImg; sourceSize.width: 30; sourceSize.height: 30; width: 30; height: 30
                x: 18; anchors.verticalCenter: parent.verticalCenter }
        Text { x: 58; anchors.verticalCenter: parent.verticalCenter; text: "SubGrab"
               color: cp.fg; font.pixelSize: 16; font.weight: Font.DemiBold }
        Row {
            x: 190; anchors.verticalCenter: parent.verticalCenter; spacing: 4
            NavTab { icn: "folder-open"; txt: "Auto Folder"; active: win.page === "auto"; onClicked: win.page = "auto" }
            NavTab { icn: "magnifying-glass"; txt: "Search"; active: win.page === "search"; onClicked: win.page = "search" }
            NavTab { icn: "broom"; txt: "Tools"; active: win.page === "tools"; onClicked: win.page = "tools" }
            NavTab { icn: "gear-six"; txt: "Settings"; active: win.page === "settings"; onClicked: win.page = "settings" }
        }
        Row {
            anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 10
            MButton { txt: "Update sources"; height: 32; onClicked: bridge.updateSources() }
            Rectangle {
                width: 92; height: 32; radius: 16; color: cp.card; border.color: cp.cardBorder
                Image { source: bridge.icon(cp.bg === "#14121B" ? "sun" : "moon", "muted"); sourceSize.width: 14; sourceSize.height: 14; width: 14; height: 14; x: 12; anchors.verticalCenter: parent.verticalCenter }
                Text { text: bridge.themeLabel(); color: cp.fg; font.pixelSize: 12
                       anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.toggleTheme() }
            }
        }
    }

    // --------------------------------------------------------------- pages
    StackLayout {
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: topbar.bottom; anchors.bottom: statusbar.top
        currentIndex: win.page === "auto" ? 0 : win.page === "search" ? 1 : win.page === "tools" ? 2 : 3

        // -------------------------------------------------------- AUTO
        Item {
            SplitView {
                id: split
                anchors.fill: parent
                Component.onCompleted: restoreTimer.start()
                Timer { id: restoreTimer; interval: 0
                        onTriggered: { var s = bridge.splitter("auto_h")
                                       if (s.length === 2 && s[0] > 100 && s[1] > 100) {
                                           leftCol.SplitView.preferredWidth = s[0]
                                           detailsCard.SplitView.preferredWidth = s[1] } } }
                Component.onDestruction: bridge.saveSplitter("auto_h", [leftCol.width, detailsCard.width])

                Item {
                    id: leftCol
                    SplitView.preferredWidth: 760
                    SplitView.minimumWidth: 440
                    Column {
                        anchors.fill: parent; anchors.margins: 14; anchors.leftMargin: 22; spacing: 12
                        Card {
                            width: parent.width; height: 84
                            Text { x: 16; y: 10; text: "Movie / series folder"; color: cp.muted; font.pixelSize: 11 }
                            MInput {
                                id: folderInput
                                anchors.left: parent.left; anchors.leftMargin: 16; anchors.right: browseBtn.left; anchors.rightMargin: 8; y: 32; icn: "folder-open"
                                hint: "Pick a folder with movies or series..."
                                Component.onCompleted: text = bridge.folder
                                onEdited: folderDebounce.restart()
                                Timer { id: folderDebounce; interval: 700; onTriggered: bridge.setFolder(folderInput.text) }
                            }
                            MButton { id: openBtn; anchors.right: scanBtn.left; anchors.rightMargin: 8; y: 32; height: 36
                                      txt: "Open"; onClicked: bridge.openFolder(folderInput.text) }
                            MButton { id: browseBtn; anchors.right: openBtn.left; anchors.rightMargin: 8; y: 32; height: 36
                                      txt: "Browse..."
                                      onClicked: { var d = bridge.browseFolder(); if (d) { folderInput.text = d; bridge.setFolder(d) } } }
                            MButton { id: scanBtn; anchors.right: parent.right; anchors.rightMargin: 16; y: 32; height: 36
                                      txt: "Scan"; primary: true; onClicked: bridge.setFolder(folderInput.text) }
                        }
                        Item {
                            width: parent.width; height: 60
                            Flow {
                                id: chipRow; spacing: 8; width: parent.width
                                MCombo { model: bridge.languages(); current: bridge.language(); onPicked: function(v) { bridge.setLanguage(v) } }
                                Chip { txt: "Include subfolders"; Component.onCompleted: on = bridge.option("include_subfolders")
                                       onToggled: function(v) { on = v; bridge.setOption("include_subfolders", v); bridge.scan() } }
                                Chip { txt: "Overwrite existing"; Component.onCompleted: on = bridge.option("overwrite")
                                       onToggled: function(v) { on = v; bridge.setOption("overwrite", v) } }
                                Chip { txt: "Convert to UTF-8"; Component.onCompleted: on = bridge.option("utf8")
                                       onToggled: function(v) { on = v; bridge.setOption("utf8", v) } }
                                Chip { txt: "Convert to SRT"; Component.onCompleted: on = bridge.option("to_srt")
                                       onToggled: function(v) { on = v; bridge.setOption("to_srt", v) } }
                                Chip { txt: "Remove ads"; Component.onCompleted: on = bridge.option("ads")
                                       onToggled: function(v) { on = v; bridge.setOption("ads", v) } }
                                Chip { txt: "Watch folder"; Component.onCompleted: on = bridge.option("watch_folder")
                                       onToggled: function(v) { on = v; bridge.setOption("watch_folder", v) } }
                            }
                        }
                        Card {
                            width: parent.width; height: parent.height - 84 - 60 - 40 - 48
                            Text { x: 16; y: 12; text: "Movies"; color: cp.muted; font.pixelSize: 11; font.weight: Font.DemiBold }
                            MInput {
                                id: movieFilter; anchors.right: parent.right; anchors.rightMargin: 10; y: 4
                                width: 200; height: 28; hint: "Filter..."; icn: "magnifying-glass"
                            }
                            ListView {
                                id: moviesList
                                anchors.fill: parent; anchors.margins: 10; anchors.topMargin: 38; clip: true
                                model: moviesModel; spacing: 6
                                delegate: Rectangle {
                                    property bool show: movieFilter.text === "" || title.toLowerCase().indexOf(movieFilter.text.toLowerCase()) >= 0 || file.toLowerCase().indexOf(movieFilter.text.toLowerCase()) >= 0
                                    width: ListView.view.width; height: show ? 58 : 0; radius: 10
                                    visible: show
                                    color: sel ? cp.accentSoft : "transparent"
                                    Rectangle { x: 10; y: 11; width: 25; height: 36; radius: 5; color: pc }
                                    Badge { id: rowBadge; anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                                            maxW: Math.round(parent.width * 0.40)
                                            txt: status; kind: tag === "ok" ? "ok" : tag === "bad" ? "bad" : tag === "review" ? "warn" : "info" }
                                    Badge { id: typeBadge; anchors.right: rowBadge.left; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter
                                            txt: mtype; kind: "info" }
                                    Text { x: 46; y: 9; width: parent.width - 58 - rowBadge.width - typeBadge.width - 20; text: title; color: cp.fg; font.pixelSize: 13; font.weight: Font.Medium; elide: Text.ElideRight }
                                    Text { x: 46; y: 30; width: parent.width - 58 - rowBadge.width - typeBadge.width - 20; text: file; color: cp.muted; font.pixelSize: 11; elide: Text.ElideMiddle }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.selectMovie(index) }
                                }
                                Text { anchors.centerIn: parent; visible: moviesList.count === 0
                                       text: "Pick a folder above - SubGrab scans it and finds subtitles for everything inside."
                                       color: cp.muted; font.pixelSize: 13; width: parent.width - 60; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter }
                            }
                        }
                        Row {
                            width: parent.width; height: 40; spacing: 10
                            MButton { txt: "Download subtitles"; primary: true; enabled2: !bridge.running; onClicked: bridge.startDownload() }
                            MButton { txt: "Stop"; enabled2: bridge.running; onClicked: bridge.stopDownload() }
                            Rectangle {
                                visible: bridge.progress >= 0; height: 8; width: 220; radius: 4; anchors.verticalCenter: parent.verticalCenter
                                color: cp.input
                                Rectangle { height: parent.height; radius: 4; color: cp.accent; width: parent.width * Math.min(1, bridge.progress) }
                            }
                        }
                    }
                }
                Card {
                    id: detailsCard
                    SplitView.preferredWidth: 420
                    SplitView.minimumWidth: 300
                    Column {
                        anchors.fill: parent; anchors.margins: 16; spacing: 10
                        Text { text: "Movie details"; color: cp.muted; font.pixelSize: 11; font.weight: Font.DemiBold }
                        Row {
                            width: parent.width; spacing: 14
                            Rectangle { width: 110; height: 162; radius: 8; color: "#1B2440"; clip: true
                                Image { anchors.fill: parent; source: bridge.details.poster || ""; fillMode: Image.PreserveAspectCrop
                                        visible: bridge.details.poster !== "" }
                                Text { anchors.centerIn: parent; visible: bridge.details.poster === ""; text: "🎬"; font.pixelSize: 28 } }
                            Column {
                                width: parent.width - 124; spacing: 6
                                Text { width: parent.width; text: bridge.details.title; color: cp.fg; font.pixelSize: 16; font.weight: Font.DemiBold; wrapMode: Text.Wrap }
                                Text { width: parent.width; text: bridge.details.meta; color: cp.muted; font.pixelSize: 12; wrapMode: Text.Wrap }
                                Badge { txt: bridge.details.chip; kind: bridge.details.chipKind }
                            }
                        }
                        Text { text: "Subtitle candidates"; color: cp.muted; font.pixelSize: 11; font.weight: Font.DemiBold }
                        ListView {
                            id: candList
                            width: parent.width; height: parent.height - 230; clip: true; spacing: 8
                            model: candidatesModel
                            delegate: Rectangle {
                                width: ListView.view.width; height: 64; radius: 10; color: cp.input; border.color: cp.cardBorder
                                Text { x: 12; y: 9; width: parent.width - 130; text: release; color: cp.fg; font.pixelSize: 12; elide: Text.ElideMiddle }
                                Text { x: 12; y: 33; width: parent.width - 130; text: why; color: cp[whyKind] ? cp[whyKind] : cp.muted; font.pixelSize: 11; elide: Text.ElideRight }
                                Badge { anchors.right: parent.right; anchors.rightMargin: 10; y: 8; txt: badge; kind: badgeKind }
                                Text { anchors.right: parent.right; anchors.rightMargin: 12; anchors.bottom: parent.bottom; anchors.bottomMargin: 7
                                       text: "Download"; color: cp.accent; font.pixelSize: 11; font.weight: Font.DemiBold
                                       MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.downloadCandidate(index) } }
                                Text { anchors.right: parent.right; anchors.rightMargin: 82; anchors.bottom: parent.bottom; anchors.bottomMargin: 7
                                       text: "Preview"; color: cp.muted; font.pixelSize: 11
                                       MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.previewCandidate(index) } }
                            }
                            Text { anchors.centerIn: parent; visible: candList.count === 0
                                   text: "Select a movie to see its subtitle candidates."; color: cp.muted; font.pixelSize: 12 }
                        }
                    }
                }
            }
        }

        // -------------------------------------------------------- SEARCH
        Item {
            Column {
                anchors.fill: parent; anchors.margins: 14; anchors.leftMargin: 22; spacing: 12
                Card {
                    width: parent.width; height: 76
                    MInput {
                        id: searchBox; x: 16; anchors.verticalCenter: parent.verticalCenter; width: 380; icn: "magnifying-glass"
                        hint: "Movie / series name or IMDb id..."
                        onAccepted: bridge.search(text, sourceCombo.current)
                    }
                    MCombo { id: sourceCombo; x: 412; anchors.verticalCenter: parent.verticalCenter
                             model: bridge.sourceNames(); current: "All sources" }
                    MButton { txt: "Search"; primary: true; anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
                              onClicked: bridge.search(searchBox.text, sourceCombo.current) }
                }
                SplitView {
                    width: parent.width; height: parent.height - 76 - 12
                    orientation: Qt.Vertical
                    Component.onCompleted: searchSplitTimer.start()
                    Timer { id: searchSplitTimer; interval: 0
                            onTriggered: { var s = bridge.splitter("search_v")
                                           if (s.length === 2 && s[0] > 60 && s[1] > 100) {
                                               resultsCard.SplitView.preferredHeight = s[0]
                                               subsCard.SplitView.preferredHeight = s[1] } } }
                    Component.onDestruction: bridge.saveSplitter("search_v", [resultsCard.height, subsCard.height])
                    Item {
                        id: resultsCard
                        SplitView.preferredHeight: Math.min(158, 46 + Math.ceil(grid.count / 5) * 62)
                        SplitView.minimumHeight: 100
                        visible: grid.count > 0
                        Column {
                            anchors.fill: parent; spacing: 6
                            Text { text: "Results"; color: cp.muted; font.pixelSize: 11; font.weight: Font.DemiBold }
                            GridView {
                                id: grid; width: parent.width; height: parent.height - 17; clip: true
                                cellWidth: 218; cellHeight: 62
                                model: resultsModel
                                property int selRes: -1
                                delegate: Rectangle {
                                    width: 208; height: 54; radius: 10; border.color: grid.selRes === index ? cp.accent : cp.cardBorder; border.width: grid.selRes === index ? 2 : 1
                                    gradient: Gradient {
                                        GradientStop { position: 0.0; color: pc }
                                        GradientStop { position: 1.0; color: Qt.darker(pc, 1.7) }
                                    }
                                    Text { x: 12; y: 7; width: 184; text: title; color: "#FFFFFF"; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight }
                                    Text { x: 12; anchors.bottom: parent.bottom; anchors.bottomMargin: 7; width: 184; text: year + (source ? " · " + source : ""); color: "#FFFFFFB0"; font.pixelSize: 11; elide: Text.ElideRight }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { grid.selRes = index; bridge.selectResult(index) } }
                                }
                            }
                        }
                    }
                    Card {
                        id: subsCard
                        SplitView.minimumHeight: 140
                        Text { x: 16; y: 12; text: "Subtitles"; color: cp.muted; font.pixelSize: 11; font.weight: Font.DemiBold }
                        ListView {
                            id: subsList
                            anchors.fill: parent; anchors.margins: 12; anchors.topMargin: 34; clip: true; spacing: 8
                            model: subsModel
                        delegate: Rectangle {
                            width: ListView.view.width; height: 56; radius: 10; color: cp.input; border.color: cp.cardBorder
                            Image { source: bridge.icon("file-video", "muted"); sourceSize.width: 17; sourceSize.height: 17; x: 12; anchors.verticalCenter: parent.verticalCenter }
                            Text { x: 40; y: 9; width: parent.width - 320; text: release; color: cp.fg; font.pixelSize: 12; elide: Text.ElideMiddle }
                            Text { x: 40; y: 31; width: parent.width - 320; text: (why ? why + " · " : "") + lang + (author ? " · by " + author : ""); color: cp.muted; font.pixelSize: 11; elide: Text.ElideRight }
                            Badge { anchors.right: parent.right; anchors.rightMargin: 224; anchors.verticalCenter: parent.verticalCenter; txt: badge; kind: badgeKind }
                            MButton { anchors.right: parent.right; anchors.rightMargin: 116; anchors.verticalCenter: parent.verticalCenter
                                      txt: "Preview"; height: 30; onClicked: bridge.previewSub(index) }
                            MButton { anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
                                      txt: "Download"; height: 30; primary: true; onClicked: bridge.downloadSub(index) }
                        }
                        Text { anchors.centerIn: parent; visible: subsList.count === 0
                               text: resultsModel.rowCount() === 0 ? "Search for a movie or series above." : "Pick a result to list its subtitles."
                               color: cp.muted; font.pixelSize: 13 }
                        }
                    }
                }
            }
        }

        // -------------------------------------------------------- TOOLS
        Flickable {
            contentHeight: toolsCol.height + 28; clip: true
            Column {
                id: toolsCol; x: 22; y: 14; width: parent.width - 44; spacing: 12
                Card {
                    width: parent.width; height: 240
                    Text { x: 16; y: 12; text: "Fix a subtitle file"; color: cp.muted; font.pixelSize: 11; font.weight: Font.DemiBold }
                    Row {
                        x: 16; y: 38; spacing: 10; width: parent.width - 32
                        MInput { id: toolFile; width: 420; hint: "Subtitle file (.srt, .ass...)" }
                        Text { text: "Browse..."; color: cp.accent; font.pixelSize: 12; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter
                               MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                           onClicked: { var f = bridge.browseSubtitleFile(); if (f) toolFile.text = f } } }
                    }
                    Row {
                        x: 16; y: 86; spacing: 10
                        Text { text: "Shift (ms):"; color: cp.fg; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        MInput { id: shiftBox; width: 90; text: "0" }
                        Repeater { model: [-1000, -500, 500, 1000]
                            MButton { txt: (modelData > 0 ? "+" : "") + modelData; height: 30
                                      onClicked: shiftBox.text = String(parseInt(shiftBox.text || "0") + modelData) } }
                        Text { text: "FPS:"; color: cp.fg; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        MInput { id: fpsFrom; width: 70; hint: "from" }
                        Text { text: "→"; color: cp.muted; anchors.verticalCenter: parent.verticalCenter }
                        MInput { id: fpsTo; width: 70; hint: "to" }
                    }
                    Row {
                        x: 16; y: 132; spacing: 16
                        Check { id: replaceCb; txt: "Replace the original (keeps a .bak copy)"
                                onToggled: function(v) { on = v } }
                    }
                    MButton { x: 16; y: 176; txt: "Apply"; primary: true
                              onClicked: bridge.toolsApply(toolFile.text, parseInt(shiftBox.text || "0"), fpsFrom.text, fpsTo.text, replaceCb.on) }
                }
                Card {
                    width: parent.width; height: 190
                    Text { x: 16; y: 12; text: "Rename video files to clean names"; color: cp.muted; font.pixelSize: 11; font.weight: Font.DemiBold }
                    Row {
                        x: 16; y: 38; spacing: 10; width: parent.width - 32
                        MInput { id: rnFolder; width: 420; hint: "Folder with videos..." }
                        Text { text: "Browse..."; color: cp.accent; font.pixelSize: 12; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter
                               MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                           onClicked: { var d = bridge.browseFolder(); if (d) rnFolder.text = d } } }
                    }
                    Row {
                        x: 16; y: 88; spacing: 10
                        MButton { txt: "Preview renames"; onClicked: bridge.planRenames(rnFolder.text) }
                        MButton { txt: "Apply renames"; primary: true; onClicked: bridge.applyRenames() }
                        MButton { txt: "Undo last rename"; onClicked: bridge.undoRenames() }
                    }
                    Text { x: 16; y: 140; width: parent.width - 32; text: "Preview shows exactly what will change before anything is renamed. Undo restores the last batch."
                           color: cp.muted; font.pixelSize: 12; wrapMode: Text.Wrap }
                }
            }
        }

        // -------------------------------------------------------- SETTINGS
        Flickable {
            objectName: "settingsFlick"
            contentHeight: setCol.height + 28; clip: true
            Column {
                id: setCol; x: 22; y: 14; width: parent.width - 44; spacing: 12
                property var st: ({})
                property var srcEnabled: ({})
                Component.onCompleted: { st = bridge.settings(); srcEnabled = (st && st.enabled) ? st.enabled : ({}) }
                Card {
                    width: parent.width; height: 292
                    Text { x: 16; y: 12; text: "General"; color: cp.muted; font.pixelSize: 11; font.weight: Font.DemiBold }
                    Grid {
                        x: 16; y: 38; columns: 2; columnSpacing: 14; rowSpacing: 12; width: parent.width - 32
                        Text { text: "Theme"; color: cp.fg; font.pixelSize: 12 }
                        MCombo { id: themeCombo; objectName: "themeCombo"; model: ["Dark", "Light"]
                                 current: setCol.st.theme === "light" ? "Light" : "Dark"
                                 onPicked: function(v) { bridge.setThemeMode(v.toLowerCase()) } }
                        Text { text: "Default subtitle language"; color: cp.fg; font.pixelSize: 12 }
                        MCombo { id: defLangCombo; model: bridge.languages(); current: setCol.st.language || "English" }
                        Text { text: "Second language (optional)"; color: cp.fg; font.pixelSize: 12 }
                        MCombo { id: lang2Combo; model: ["None"].concat(bridge.languages()); current: setCol.st.language2 || "None" }
                        Text { text: "Download folder"; color: cp.fg; font.pixelSize: 12 }
                        Row { spacing: 10
                            MInput { id: destInput; width: 380; text: setCol.st.dest || "" }
                            Text { text: "Browse..."; color: cp.accent; font.pixelSize: 12; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter
                                   MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                               onClicked: { var d = bridge.browseFolder(); if (d) destInput.text = d } } } }
                    }
                    Row {
                        x: 16; y: 246; spacing: 22
                        Check { id: askCb; txt: "Ask where to save every time"; Component.onCompleted: on = !!setCol.st.ask_dest
                                onToggled: function(v) { on = v } }
                        Check { id: extractCb; txt: "Extract .zip files after download"; Component.onCompleted: on = !!setCol.st.extract
                                onToggled: function(v) { on = v } }
                        Check { id: updatesCb; txt: "Check for updates on start"; Component.onCompleted: on = !!setCol.st.check_updates
                                onToggled: function(v) { on = v } }
                    }
                }
                Card {
                    width: parent.width; height: 360
                    Text { x: 16; y: 12; text: "Sources"; color: cp.muted; font.pixelSize: 11; font.weight: Font.DemiBold }
                    ListView {
                        x: 16; y: 34; width: parent.width - 32; height: 216; spacing: 6; clip: true
                        model: sourcesModel
                        delegate: Row {
                            width: ListView.view.width; height: 30; spacing: 10
                            Check { txt: name; width: 200; Component.onCompleted: on = !!enabled
                                    onToggled: function(v) { on = v; setCol.srcEnabled[name] = v } }
                            Text { width: 320; text: note; color: cp.muted; font.pixelSize: 11; elide: Text.ElideRight; anchors.verticalCenter: parent.verticalCenter }
                            Text { text: "Test"; color: cp.accent; font.pixelSize: 12; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter
                                   MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.testSource(name) } }
                            Text { text: status; color: cp[statusKind] ? cp[statusKind] : cp.muted; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        }
                    }
                    Text { x: 16; y: 258; text: "Keys and accounts"; color: cp.muted; font.pixelSize: 11; font.weight: Font.DemiBold }
                    Row {
                        x: 16; y: 278; spacing: 10; width: parent.width - 32
                        MInput { id: ssKey; width: 250; hint: "SubSource API key"; password: true; text: setCol.st.subsource_key || "" }
                        MInput { id: osKey; width: 250; hint: "OpenSubtitles API key"; password: true; text: setCol.st.os_key || "" }
                        MInput { id: osUser; width: 170; hint: "OS username"; text: setCol.st.os_user || "" }
                        MInput { id: osPass; width: 170; hint: "OS password"; password: true; text: setCol.st.os_pass || "" }
                    }
                    Text { x: 16; y: 322; text: "Stored in: " + (setCol.st.secrets_store || ""); color: cp.muted; font.pixelSize: 11 }
                }
                Card {
                    width: parent.width; height: 170
                    Text { x: 16; y: 12; text: "Subtitles"; color: cp.muted; font.pixelSize: 11; font.weight: Font.DemiBold }
                    Flow {
                        x: 16; y: 38; width: parent.width - 32; spacing: 14
                        Check { id: cUtf; txt: "Convert to UTF-8"; Component.onCompleted: on = setCol.st.clean ? !!setCol.st.clean.utf8 : true; onToggled: function(v) { on = v } }
                        Check { id: cSrt; txt: "Convert to SRT"; Component.onCompleted: on = setCol.st.clean ? !!setCol.st.clean.to_srt : true; onToggled: function(v) { on = v } }
                        Check { id: cAds; txt: "Remove ads / watermarks"; Component.onCompleted: on = setCol.st.clean ? !!setCol.st.clean.ads : false; onToggled: function(v) { on = v } }
                        Check { id: cHi; txt: "Remove hearing-impaired tags"; Component.onCompleted: on = setCol.st.clean ? !!setCol.st.clean.hi : false; onToggled: function(v) { on = v } }
                        Check { id: cBom; txt: "Add BOM (older TVs)"; Component.onCompleted: on = setCol.st.clean ? !!setCol.st.clean.bom : false; onToggled: function(v) { on = v } }
                        Check { id: cHash; txt: "Use file hash when possible (exact sync)"; Component.onCompleted: on = !!setCol.st.use_hash; onToggled: function(v) { on = v } }
                        Check { id: cWeak; txt: "Save weak matches automatically"; Component.onCompleted: on = !!setCol.st.weak_save; onToggled: function(v) { on = v } }
                    }
                    Text { x: 16; y: 128; width: parent.width - 32; text: "7-Zip unpacks RAR/7z downloads: " + (setCol.st.sevenzip_found ? "found ✓" : "not found - zip and .srt still work.")
                           color: cp.muted; font.pixelSize: 12 }
                }
                Card {
                    width: parent.width; height: 236
                    Text { x: 16; y: 12; text: "About"; color: cp.muted; font.pixelSize: 11; font.weight: Font.DemiBold }
                    Image { x: 16; y: 36; source: win.logoImg; sourceSize.width: 56; sourceSize.height: 56 }
                    Text { x: 86; y: 40; text: bridge.appInfo().name + " " + bridge.appInfo().version; color: cp.fg; font.pixelSize: 18; font.weight: Font.DemiBold }
                    Text { x: 86; y: 66; width: parent.width - 110
                           text: "Subtitle downloader - OpenSubtitles, SubSource and Subf2m.\nGPL v3 licensed. 7-Zip (LGPL) is used for RAR/7z when available.\nIcons: Phosphor Icons (MIT) - phosphoricons.com · Font: Inter (OFL)"
                           color: cp.muted; font.pixelSize: 12; wrapMode: Text.Wrap }
                    MButton { x: 16; y: 116; txt: "Check for updates"; onClicked: bridge.checkUpdates() }
                    MButton { x: 170; y: 116; txt: "Open debug log"; onClicked: bridge.openDataPath("log") }
                    MButton { x: 320; y: 116; txt: "Open data folder"; onClicked: bridge.openDataPath("data") }
                    MButton { x: parent.width - width - 16; y: 116; txt: "Support me on Ko-fi"; primary: true; onClicked: bridge.openUrl("https://ko-fi.com/megatronazx") }
                    Rectangle { x: 16; y: 164; width: parent.width - 32; height: 1; color: cp.cardBorder }
                    Text { x: 16; y: 180; width: parent.width - 270
                           text: "Also by us: Giant Media Manager. Organize your library, fetch metadata and posters, and keep file names clean."
                           color: cp.fg; font.pixelSize: 13; wrapMode: Text.Wrap }
                    MButton { x: parent.width - width - 16; y: 180; txt: "Giant Media Manager page"
                              onClicked: bridge.openUrl("https://github.com/Megatro-nn/Giant-Media-Manager") }
                }
                Row {
                    spacing: 12; height: 46
                    MButton { txt: "Save settings"; primary: true; height: 40
                              onClicked: {
                                  bridge.saveSettings({
                                      ui_lang: "en",
                                      theme: themeCombo.current.toLowerCase(),
                                      language: defLangCombo.current,
                                      language2: lang2Combo.current === "None" ? "" : lang2Combo.current,
                                      dest: destInput.text, ask_dest: askCb.on, extract: extractCb.on,
                                      check_updates: updatesCb.on, use_hash: cHash.on, weak_save: cWeak.on,
                                      clean: { utf8: cUtf.on, to_srt: cSrt.on, ads: cAds.on, hi: cHi.on, bom: cBom.on },
                                      enabled: setCol.srcEnabled,
                                      subsource_key: ssKey.text, os_key: osKey.text, os_user: osUser.text, os_pass: osPass.text
                                  })
                              } }
                }
            }
        }
    }

    // ----------------------------------------------------------- status bar
    Rectangle {
        id: statusbar; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 34; color: cp.rail
        Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: cp.cardBorder }
        Text { x: 22; anchors.verticalCenter: parent.verticalCenter; width: parent.width * 0.5; elide: Text.ElideRight
               text: bridge.statusText; color: cp.muted; font.pixelSize: 11 }
        Row {
            anchors.right: parent.right; anchors.rightMargin: 18; anchors.verticalCenter: parent.verticalCenter; spacing: 12
            Repeater {
                model: bridge.sourcesHealth
                delegate: Row {
                    spacing: 5
                    Rectangle { width: 7; height: 7; radius: 4; color: modelData.color; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: modelData.name; color: cp.muted; font.pixelSize: 10 }
                }
            }
        }
    }

    // --------------------------------------------------------------- toast
    Rectangle {
        id: toast; visible: false; anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 56
        width: toastTxt.implicitWidth + 40; height: 40; radius: 12; color: cp.card; border.color: cp.accent
        Text { id: toastTxt; anchors.centerIn: parent; color: cp.fg; font.pixelSize: 13 }
    }

    // ---------------------------------------------------------- preview dlg
    Dialog {
        id: previewDlg; modal: true; anchors.centerIn: parent
        width: Math.min(720, win.width - 80); height: Math.min(560, win.height - 80)
        background: Rectangle { color: cp.card; radius: 14; border.color: cp.cardBorder }
        header: Text { id: previewTitle; padding: 14; color: cp.fg; font.pixelSize: 15; font.weight: Font.DemiBold }
        contentItem: ScrollView {
            clip: true
            TextArea {
                id: previewText; readOnly: true; wrapMode: Text.Wrap; color: cp.fg
                font.family: "Consolas"; font.pixelSize: 12
                background: Rectangle { color: "transparent" }
            }
        }
    }
}
