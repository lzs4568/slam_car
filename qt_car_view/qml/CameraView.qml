import QtQuick 2.15

// YOLO 画面 — ROS2 image://yolo/ provider 直连 (零拷贝, 无HTTP开销)
Rectangle {
    id: root
    color: "#C0C8D0"

    property bool   streaming: false
    property string resolution: "--"
    property string elfHost: "elf2-desktop.local"
    property int    _seq: 0

    // ── 标题栏 ──
    Rectangle {
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 24; color: "#6B7B8B"
        Text {
            anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
            text: "CAMERA FEED  |  ROS2 DDS (自动发现, 无需IP)"
            color: "#F0F2F4"; font { pixelSize: 11; bold: true; family: "monospace" }
        }
        Rectangle {
            id: statusLed
            anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
            width: 8; height: 8; radius: 4
            color: "#E74C3C"; border { width: 1; color: "#C0392B" }
        }
    }

    // ── 16:9 视频 ──
    Rectangle {
        id: videoArea
        anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 24 }
        height: width * 9 / 16; color: "#1a1a1a"
        Rectangle { anchors { fill: parent; margins: 4 } color: "transparent"; border { width: 2; color: "#505860" } }

        Image {
            id: videoImage
            anchors { fill: parent; margins: 5 }
            fillMode: Image.PreserveAspectFit
            source: "image://yolo/frame?" + root._seq
            cache: false

            onStatusChanged: {
                if (status === Image.Ready) {
                    if (!root.streaming) root.streaming = true
                    root.resolution = sourceSize.width + "x" + sourceSize.height
                    statusLed.color = "#27AE60"; statusLed.border.color = "#1E8449"
                } else if (status === Image.Error) {
                    root.streaming = false
                    statusLed.color = "#E74C3C"; statusLed.border.color = "#C0392B"
                }
            }
        }

        // 无信号
        Item {
            anchors.fill: parent
            visible: !root.streaming
            Rectangle { anchors.centerIn: parent; width: parent.width * 0.6; height: 1; color: "#333" }
            Rectangle { anchors.centerIn: parent; width: 1; height: parent.height * 0.6; color: "#333" }
            Column {
                anchors.centerIn: parent; spacing: 6
                Text { text: "NO SIGNAL"; color: "#505860"; font { pixelSize: 16; bold: true; family: "monospace" } anchors.horizontalCenter: parent.horizontalCenter }
                Text { text: "等待 ROS2 /yolo/annotated..."; color: "#404850"; font { pixelSize: 11; family: "monospace" } anchors.horizontalCenter: parent.horizontalCenter }
            }
        }

        // 底部状态
        Rectangle {
            anchors { left: parent.left; bottom: parent.bottom; margins: 8 }
            color: "#000000"; opacity: 0.7
            width: infoRow.width + 16; height: infoRow.height + 6
            Row { id: infoRow; anchors.centerIn: parent; spacing: 12
                Text { text: "CAM-01"; color: "#4CAF50"; font { pixelSize: 10; family: "monospace" } }
                Text { text: "|"; color: "#505860"; font { pixelSize: 10; family: "monospace" } }
                Text { text: root.resolution; color: "#4CAF50"; font { pixelSize: 10; family: "monospace" } }
                Text { text: "|"; color: "#505860"; font { pixelSize: 10; family: "monospace" } }
                Text { text: "ROS2/DDS"; color: "#4CAF50"; font { pixelSize: 10; family: "monospace" } }
            }
        }
    }

    // ── 50ms 刷新 (20fps) — 只改 source 触发 provider 查询 ──
    Timer {
        id: tick
        interval: 50
        repeat: true
        running: true
        onTriggered: {
            root._seq++
        }
    }

    onStreamingChanged: {
        if (!streaming) root._seq = 0
    }
}
