import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtWebEngine 1.10

ApplicationWindow {
    id: mainWindow
    visible: true
    width: 1500
    height: 900
    title: "巡检小车监控平台"
    color: "#BCC4CC"

    // --- Internal state ---
    property var activeAlarms: ({})
    property double _lastLat: 0
    property double _lastLng: 0

    // 每 500ms 读 GPS 坐标推给地图 (主线程,可靠)
    Timer {
        interval: 500; running: true; repeat: true
        onTriggered: {
            var lat = dataManager.latitude
            var lng = dataManager.longitude
            if (lat === 0 || lng === 0) return
            if (lat === _lastLat && lng === _lastLng) return
            _lastLat = lat; _lastLng = lng
            mapView.updatePosition(lat, lng)
        }
    }

    // --- Top Bar ---
    Rectangle {
        id: topBar
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 40
        color: "#7B8B9B"

        // 标题
        Text {
            anchors { left: parent.left; leftMargin: 14; verticalCenter: parent.verticalCenter }
            text: "INSPECTION VEHICLE MONITOR V2.0"
            color: "#F0F2F4"
            font { pixelSize: 14; bold: true; family: "monospace" }
        }

        // 状态指示
        StatusBar {
            id: statusBar
            anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
        }

        // 底部金属线
        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 2
            color: "#5D6D7E"
        }
    }

    // --- Main Content: 3-column layout ---
    RowLayout {
        anchors {
            left: parent.left; right: parent.right
            top: topBar.bottom; bottom: bottomBar.top
            margins: 6
        }
        spacing: 6

        // Column 1: Sensor Panel
        Rectangle {
            Layout.preferredWidth: 300
            Layout.fillHeight: true
            color: "#BCC4CC"

            // 外框（立体凹陷）
            Rectangle {
                anchors { fill: parent }
                color: "transparent"
                border { width: 2; color: "#9098A0" }
                Rectangle {
                    anchors { fill: parent; margins: 2 }
                    color: "transparent"
                    border { width: 1; color: "#D0D4D8" }
                }
            }

            SensorPanel {
                id: sensorPanel
                anchors { fill: parent; margins: 4 }
            }
        }

        // Column 2: Map (center)
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#BCC4CC"

            Rectangle {
                anchors { fill: parent }
                color: "transparent"
                border { width: 2; color: "#9098A0" }
                Rectangle {
                    anchors { fill: parent; margins: 2 }
                    color: "transparent"
                    border { width: 1; color: "#D0D4D8" }
                }
            }

            MapWebView {
                id: mapView
                anchors { fill: parent; margins: 4 }
                apiKey: settingsManager ? settingsManager.amapApiKey : ""

                onMapClicked: function(lat, lng) {
                    dataManager.onWaypointSelected(lat, lng)
                }
                onPlaceNavigateRequested: function(lat, lng, name) {
                    dataManager.onWaypointSelected(lat, lng)
                    statusText.text = "前往: " + name
                }
                onPlaceAnnotateRequested: function(lat, lng, name) {
                    if (ros2Bridge) ros2Bridge.publishAnnotation(name, lat, lng)
                    statusText.text = "标注: " + name
                    // 同时标个临时蓝点
                    mapView.showWaypoint(lat, lng)
                }
            }
        }

        // Column 3: Camera + Direction Pad (right)
        Rectangle {
            Layout.preferredWidth: 800
            Layout.fillHeight: true
            color: "#BCC4CC"

            Rectangle {
                anchors { fill: parent }
                color: "transparent"
                border { width: 2; color: "#9098A0" }
                Rectangle {
                    anchors { fill: parent; margins: 2 }
                    color: "transparent"
                    border { width: 1; color: "#D0D4D8" }
                }
            }

            ColumnLayout {
                anchors { fill: parent; margins: 4 }
                spacing: 6

                // Camera — 16:9 aspect, max height constrained
                CameraView {
                    id: cameraView
                    Layout.fillWidth: true
                    Layout.preferredHeight: cameraView.width * 9 / 16
                }

                // 方向盘 与 对话框 左右并排 (B1)
                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 6

                    DirectionPad {
                        id: dirPad
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        onCmdVelChanged: function(lx, az) {
                            if (ros2Bridge) ros2Bridge.publishCmdVel(lx, az)
                        }
                    }

                    ChatPanel {
                        id: chatPanel
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                    }
                }
            }
        }
    }

    // --- Keyboard handling (WASD) — on the direction pad itself ---
    Component.onCompleted: dirPad.forceActiveFocus()

    // --- Bottom Control Bar ---
    Rectangle {
        id: bottomBar
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 40
        color: "#9AA8B4"

        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 2
            color: "#D0D4D8"
        }

        RowLayout {
            anchors { fill: parent; margins: 6 }
            spacing: 8

            Button {
                id: collectBtn
                text: checked ? "STOP" : "START"
                checkable: true
                onToggled: {
                    if (checked) mqttClient.connect()
                    else mqttClient.disconnect()
                }
                font { family: "monospace"; bold: true; pixelSize: 12 }
            }

            Button {
                text: "CLEAR"
                onClicked: { dataManager.clearTrajectory(); mapView.clearWaypoints() }
                font { family: "monospace"; bold: true; pixelSize: 12 }
            }

            Button {
                text: "REPLAY"
                onClicked: {
                    var points = dataManager.getTrajectory()
                    if (points.length === 0) {
                        statusText.text = "NO DATA"
                        return
                    }
                    mapView.replayTrajectory(JSON.stringify(points))
                    statusText.text = "REPLAY " + points.length + " PTS"
                }
                font { family: "monospace"; bold: true; pixelSize: 12 }
            }

            Item { Layout.fillWidth: true }

            Text {
                id: statusText
                text: "READY"
                color: "#2C3E50"
                font { pixelSize: 12; bold: true; family: "monospace" }
            }

            // Settings menu buttons
            Button {
                text: "THRESHOLD"
                onClicked: { thresholdDialog.loadThresholds(); thresholdDialog.open() }
                font { family: "monospace"; pixelSize: 11 }
            }
            Button {
                text: "CONFIG"
                onClicked: { connectionDialog.loadConfig(); connectionDialog.open() }
                font { family: "monospace"; pixelSize: 11 }
            }
        }
    }

    // --- Connections ---
    Connections {
        target: dataManager
        function onSensorDisplay(data) { sensorPanel.sensorData = data }
        function onGpsDisplay(lat, lng) {
            var now = new Date()
            statusBar.gpsLat = lat
            statusBar.gpsLng = lng
            statusBar.lastUpdate = now.toLocaleTimeString(Qt.locale(), "hh:mm:ss")
            statusText.text = lat.toFixed(6) + "," + lng.toFixed(6)
        }
        function onTrajectoryPoint(lat, lng) { }
        function onTrajectoryClear() { mapView.clearTrajectory() }
        function onAlarmTriggered(sensor, direction) {
            var newAlarms = Object.assign({}, activeAlarms)
            newAlarms[sensor] = direction
            activeAlarms = newAlarms
            sensorPanel.alarms = activeAlarms
        }
        function onAlarmCleared(sensor) {
            var newAlarms = Object.assign({}, activeAlarms)
            delete newAlarms[sensor]
            activeAlarms = newAlarms
            sensorPanel.alarms = activeAlarms
        }
        function onWaypointMarker(lat, lng) { mapView.showWaypoint(lat, lng) }
        function onPlacesUpdated(json) { mapView.showPlaces(json) }
    }

    Connections {
        target: mqttClient
        function onConnectionStatus(connected) { statusBar.mqttConnected = connected }
        function onErrorMessage(msg) { statusText.text = msg }
    }

    Connections {
        target: iotdaApi
        function onDeviceStatus(online) { statusBar.deviceOnline = online }
    }

    Connections {
        target: ros2Bridge
        function onRosStatus(ready) { statusBar.ros2Ready = ready }
        function onChatMessage(role, text) { chatPanel.appendMessage(role, text) }
    }

    // --- Dialogs ---
    ConnectionDialog {
        id: connectionDialog
        cfgManager: settingsManager
    }

    ThresholdDialog {
        id: thresholdDialog
        dataMgr: dataManager
    }

    Component.onDestruction: {
        ros2Bridge.stop()
        mqttClient.disconnect()
    }
}
