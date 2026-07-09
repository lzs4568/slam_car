import QtQuick 2.15

// 明亮工业风 — 立体金属卡片
Rectangle {
    id: root

    property string sensorName: ""
    property string sensorUnit: ""
    property string sensorKey: ""
    property color accentColor: "#888"
    property double value: 0
    property bool hasData: false
    property bool alarmActive: false

    height: 120
    radius: 0
    color: "#D8DCE0"

    // 顶部/左侧浅色立体斜边
    Rectangle {
        anchors { left: parent.left; top: parent.top; right: parent.right }
        height: 2
        color: "#F0F2F4"
    }
    Rectangle {
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        width: 2
        color: "#F0F2F4"
    }
    // 底部/右侧深色阴影边
    Rectangle {
        anchors { left: parent.left; bottom: parent.bottom; right: parent.right }
        height: 2
        color: "#A0A8B0"
    }
    Rectangle {
        anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
        width: 2
        color: "#A0A8B0"
    }

    // 左侧色条
    Rectangle {
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        anchors.leftMargin: 2
        width: 5
        color: alarmActive ? "#E74C3C" : root.accentColor
    }

    // 告警时整卡红色叠加
    Rectangle {
        anchors.fill: parent
        color: "#E74C3C"
        opacity: alarmActive ? 0.12 : 0
    }

    Column {
        anchors { fill: parent; margins: 14 }
        spacing: 4

        Row {
            spacing: 8
            Rectangle {
                width: 15; height: 15; radius: 5
                color: alarmActive ? "#E74C3C"
                     : root.hasData ? "#27AE60" : "#A0A8B0"
                anchors.verticalCenter: parent.verticalCenter
                // 立体指示灯
                border { width: 1; color: alarmActive ? "#C0392B" : root.hasData ? "#1E8449" : "#888" }
            }
            Text {
                text: root.sensorName
                color: "#2C3E50"
                font { pixelSize: 13; bold: true; family: "monospace" }
            }
        }

        Row {
            spacing: 6
            Text {
                id: valueText
                text: root.hasData ? Number(root.value).toFixed(1) : "--"
                color: "#1a1a1a"
                font { pixelSize: 26; bold: true; family: "monospace" }
            }
            Text {
                text: root.sensorUnit
                color: "#607080"
                font { pixelSize: 14; family: "monospace" }
                anchors.baseline: valueText.baseline
            }
        }

        // 迷你进度条（纯装饰）
        Rectangle {
            width: parent.width
            height: 3
            color: "#B0B8C0"
            Rectangle {
                anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                width: parent.width * Math.min(root.value / (root.sensorKey === "battery" ? 15 : 100), 1.0)
                color: root.accentColor
            }
        }
    }
}
