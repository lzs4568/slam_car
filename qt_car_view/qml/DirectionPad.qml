import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 十字方向控制板 + 速度滑块 — WASD 键盘联动
FocusScope {
    id: root

    signal cmdVelChanged(double linearX, double angularZ)

    focus: true
    Keys.onPressed: {
        if (event.key === Qt.Key_W) forwardActive = true
        else if (event.key === Qt.Key_S) backwardActive = true
        else if (event.key === Qt.Key_A) leftActive = true
        else if (event.key === Qt.Key_D) rightActive = true
    }
    Keys.onReleased: {
        if (event.key === Qt.Key_W) forwardActive = false
        else if (event.key === Qt.Key_S) backwardActive = false
        else if (event.key === Qt.Key_A) leftActive = false
        else if (event.key === Qt.Key_D) rightActive = false
    }

    property bool forwardActive: false
    property bool backwardActive: false
    property bool leftActive: false
    property bool rightActive: false

    // ---- 速度参数 ----
    property double linearSpeed: 0.5
    property double angularSpeed: 0.5

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---- 方向按键区域 ----
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            // 中心点
            Item {
                id: centerItem
                width: 44; height: 44
                anchors.centerIn: parent
            }

            // -- 前进 (W) --
            Rectangle {
                id: btnForward
                anchors { horizontalCenter: parent.horizontalCenter; bottom: centerItem.top; bottomMargin: 30 }
                width: 100; height: 100; radius: 20
                color: forwardActive ? "#E67E22" : "#C0C8D0"

                Rectangle {
                    color: forwardActive ? "transparent" : "#E8ECF0"
                    height: forwardActive ? 0 : 3
                    anchors { left: parent.left; top: parent.top; right: parent.right }
                }
                Rectangle {
                    color: forwardActive ? "transparent" : "#E8ECF0"
                    width: forwardActive ? 0 : 3
                    anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                }
                Rectangle {
                    color: forwardActive ? "transparent" : "#9098A0"
                    height: forwardActive ? 0 : 3
                    anchors { left: parent.left; bottom: parent.bottom; right: parent.right }
                }
                Rectangle {
                    color: forwardActive ? "transparent" : "#9098A0"
                    width: forwardActive ? 0 : 3
                    anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
                }

                Column {
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: forwardActive ? 2 : 1
                    spacing: 2
                    Text {
                        text: "FORWARD"
                        color: forwardActive ? "#FFF" : "#2C3E50"
                        font { pixelSize: 13; bold: true; family: "monospace" }
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Text {
                        text: "[W]"
                        color: forwardActive ? "#FFE0C0" : "#7B8B9B"
                        font { pixelSize: 9; family: "monospace" }
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onPressed: forwardActive = true
                    onReleased: forwardActive = false
                }
            }

            // -- 后退 (S) --
            Rectangle {
                id: btnBackward
                anchors { horizontalCenter: parent.horizontalCenter; top: centerItem.bottom; topMargin: 30 }
                width: 100; height: 100; radius: 20
                color: backwardActive ? "#E67E22" : "#C0C8D0"

                Rectangle {
                    color: backwardActive ? "transparent" : "#E8ECF0"
                    height: backwardActive ? 0 : 3
                    anchors { left: parent.left; top: parent.top; right: parent.right }
                }
                Rectangle {
                    color: backwardActive ? "transparent" : "#E8ECF0"
                    width: backwardActive ? 0 : 3
                    anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                }
                Rectangle {
                    color: backwardActive ? "transparent" : "#9098A0"
                    height: backwardActive ? 0 : 3
                    anchors { left: parent.left; bottom: parent.bottom; right: parent.right }
                }
                Rectangle {
                    color: backwardActive ? "transparent" : "#9098A0"
                    width: backwardActive ? 0 : 3
                    anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
                }

                Column {
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: backwardActive ? 2 : 1
                    spacing: 2
                    Text {
                        text: "BACK"
                        color: backwardActive ? "#FFF" : "#2C3E50"
                        font { pixelSize: 13; bold: true; family: "monospace" }
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Text {
                        text: "[S]"
                        color: backwardActive ? "#FFE0C0" : "#7B8B9B"
                        font { pixelSize: 9; family: "monospace" }
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onPressed: backwardActive = true
                    onReleased: backwardActive = false
                }
            }

            // -- 左转 (A) --
            Rectangle {
                id: btnLeft
                anchors { verticalCenter: parent.verticalCenter; right: centerItem.left; rightMargin: 30 }
                width: 100; height: 100; radius: 20
                color: leftActive ? "#E67E22" : "#C0C8D0"

                Rectangle {
                    color: leftActive ? "transparent" : "#E8ECF0"
                    height: leftActive ? 0 : 3
                    anchors { left: parent.left; top: parent.top; right: parent.right }
                }
                Rectangle {
                    color: leftActive ? "transparent" : "#E8ECF0"
                    width: leftActive ? 0 : 3
                    anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                }
                Rectangle {
                    color: leftActive ? "transparent" : "#9098A0"
                    height: leftActive ? 0 : 3
                    anchors { left: parent.left; bottom: parent.bottom; right: parent.right }
                }
                Rectangle {
                    color: leftActive ? "transparent" : "#9098A0"
                    width: leftActive ? 0 : 3
                    anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
                }

                Column {
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: leftActive ? 2 : 1
                    spacing: 2
                    Text {
                        text: "LEFT"
                        color: leftActive ? "#FFF" : "#2C3E50"
                        font { pixelSize: 13; bold: true; family: "monospace" }
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Text {
                        text: "[A]"
                        color: leftActive ? "#FFE0C0" : "#7B8B9B"
                        font { pixelSize: 9; family: "monospace" }
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onPressed: leftActive = true
                    onReleased: leftActive = false
                }
            }

            // -- 右转 (D) --
            Rectangle {
                id: btnRight
                anchors { verticalCenter: parent.verticalCenter; left: centerItem.right; leftMargin: 30 }
                width: 100; height: 100; radius: 20
                color: rightActive ? "#E67E22" : "#C0C8D0"

                Rectangle {
                    color: rightActive ? "transparent" : "#E8ECF0"
                    height: rightActive ? 0 : 3
                    anchors { left: parent.left; top: parent.top; right: parent.right }
                }
                Rectangle {
                    color: rightActive ? "transparent" : "#E8ECF0"
                    width: rightActive ? 0 : 3
                    anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                }
                Rectangle {
                    color: rightActive ? "transparent" : "#9098A0"
                    height: rightActive ? 0 : 3
                    anchors { left: parent.left; bottom: parent.bottom; right: parent.right }
                }
                Rectangle {
                    color: rightActive ? "transparent" : "#9098A0"
                    width: rightActive ? 0 : 3
                    anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
                }

                Column {
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: rightActive ? 2 : 1
                    spacing: 2
                    Text {
                        text: "RIGHT"
                        color: rightActive ? "#FFF" : "#2C3E50"
                        font { pixelSize: 13; bold: true; family: "monospace" }
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Text {
                        text: "[D]"
                        color: rightActive ? "#FFE0C0" : "#7B8B9B"
                        font { pixelSize: 9; family: "monospace" }
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onPressed: rightActive = true
                    onReleased: rightActive = false
                }
            }

            // -- 中心停止 --
            Rectangle {
                id: stopCenter
                width: 70; height: 70; radius: 35
                anchors.centerIn: parent
                color: (forwardActive || backwardActive || leftActive || rightActive) ? "#2C3E50" : "#6B7B8B"
                border { width: 2; color: "#505860" }

                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        forwardActive = false
                        backwardActive = false
                        leftActive = false
                        rightActive = false
                    }
                }

                Text {
                    text: "STOP"
                    color: "#D0D4D8"
                    font { pixelSize: 8; bold: true; family: "monospace" }
                    anchors.centerIn: parent
                }
            }
        }

        // ---- 速度滑块 ----
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 70
            color: "transparent"

            RowLayout {
                anchors { fill: parent; margins: 8 }
                spacing: 10

                // 线速度滑块 (前进/后退)
                Text {
                    text: "LIN"
                    color: "#2C3E50"
                    font { pixelSize: 11; bold: true; family: "monospace" }
                }
                Slider {
                    id: linearSlider
                    Layout.fillWidth: true
                    from: 0.1; to: 1.0; value: 0.5; stepSize: 0.05
                    onValueChanged: root.linearSpeed = value
                    background: Rectangle {
                        x: linearSlider.leftPadding
                        y: linearSlider.topPadding + linearSlider.availableHeight / 2 - 3
                        implicitWidth: 200; implicitHeight: 6
                        width: linearSlider.availableWidth; height: implicitHeight
                        radius: 3
                        color: "#9098A0"
                        Rectangle {
                            width: linearSlider.visualPosition * parent.width
                            height: parent.height
                            radius: 3
                            color: "#E67E22"
                        }
                    }
                    handle: Rectangle {
                        x: linearSlider.leftPadding + linearSlider.visualPosition * (linearSlider.availableWidth - width)
                        y: linearSlider.topPadding + linearSlider.availableHeight / 2 - height / 2
                        implicitWidth: 18; implicitHeight: 18
                        radius: 9
                        color: "#E67E22"
                        border { width: 2; color: "#D35400" }
                    }
                }
                Text {
                    text: root.linearSpeed.toFixed(2)
                    color: "#2C3E50"
                    font { pixelSize: 13; bold: true; family: "monospace" }
                    Layout.preferredWidth: 36
                }

                // 角速度滑块 (左右转)
                Text {
                    text: "ANG"
                    color: "#2C3E50"
                    font { pixelSize: 11; bold: true; family: "monospace" }
                }
                Slider {
                    id: angularSlider
                    Layout.fillWidth: true
                    from: 0.1; to: 1.0; value: 0.5; stepSize: 0.05
                    onValueChanged: root.angularSpeed = value
                    background: Rectangle {
                        x: angularSlider.leftPadding
                        y: angularSlider.topPadding + angularSlider.availableHeight / 2 - 3
                        implicitWidth: 200; implicitHeight: 6
                        width: angularSlider.availableWidth; height: implicitHeight
                        radius: 3
                        color: "#9098A0"
                        Rectangle {
                            width: angularSlider.visualPosition * parent.width
                            height: parent.height
                            radius: 3
                            color: "#E67E22"
                        }
                    }
                    handle: Rectangle {
                        x: angularSlider.leftPadding + angularSlider.visualPosition * (angularSlider.availableWidth - width)
                        y: angularSlider.topPadding + angularSlider.availableHeight / 2 - height / 2
                        implicitWidth: 18; implicitHeight: 18
                        radius: 9
                        color: "#E67E22"
                        border { width: 2; color: "#D35400" }
                    }
                }
                Text {
                    text: root.angularSpeed.toFixed(2)
                    color: "#2C3E50"
                    font { pixelSize: 13; bold: true; family: "monospace" }
                    Layout.preferredWidth: 36
                }
            }
        }
    }

    // -- 状态变化 emit cmd_vel --
    onForwardActiveChanged: emitCmdVel()
    onBackwardActiveChanged: emitCmdVel()
    onLeftActiveChanged: emitCmdVel()
    onRightActiveChanged: emitCmdVel()
    onLinearSpeedChanged: if (forwardActive || backwardActive) emitCmdVel()
    onAngularSpeedChanged: if (leftActive || rightActive) emitCmdVel()

    function emitCmdVel() {
        var lx = 0.0
        var az = 0.0
        if (forwardActive) lx = root.linearSpeed
        else if (backwardActive) lx = -root.linearSpeed
        if (leftActive) az = root.angularSpeed
        else if (rightActive) az = -root.angularSpeed
        root.cmdVelChanged(lx, az)
    }
}
