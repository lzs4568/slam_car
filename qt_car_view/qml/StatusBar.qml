import QtQuick 2.15

Row {
    id: root
    property bool mqttConnected: false
    property bool ros2Ready: false
    property bool deviceOnline: false
    property double gpsLat: 0
    property double gpsLng: 0
    property string lastUpdate: "--"
    spacing: 20

    Row { spacing: 4
        Rectangle {
            width: 8; height: 8; radius: 4
            color: root.mqttConnected ? "#27AE60" : "#E74C3C"
            anchors.verticalCenter: parent.verticalCenter
            border { width: 1; color: root.mqttConnected ? "#1E8449" : "#C0392B" }
        }
        Text {
            text: "MQTT"
            color: "#2C3E50"
            font { pixelSize: 12; bold: true; family: "monospace" }
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    Row { spacing: 4
        Rectangle {
            width: 8; height: 8; radius: 4
            color: root.deviceOnline ? "#27AE60" : "#F39C12"
            anchors.verticalCenter: parent.verticalCenter
            border { width: 1; color: root.deviceOnline ? "#1E8449" : "#D68910" }
        }
        Text {
            text: "DEVICE"
            color: "#2C3E50"
            font { pixelSize: 12; bold: true; family: "monospace" }
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    Row { spacing: 4
        Rectangle {
            width: 8; height: 8; radius: 4
            color: root.ros2Ready ? "#27AE60" : "#F39C12"
            anchors.verticalCenter: parent.verticalCenter
            border { width: 1; color: root.ros2Ready ? "#1E8449" : "#D68910" }
        }
        Text {
            text: "ROS2"
            color: "#2C3E50"
            font { pixelSize: 12; bold: true; family: "monospace" }
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    Rectangle { width: 1; height: 14; color: "#A0A8B0"; anchors.verticalCenter: parent.verticalCenter }

    Text {
        text: "GPS: " + (root.gpsLat !== 0 || root.gpsLng !== 0
              ? root.gpsLat.toFixed(6) + " " + root.gpsLng.toFixed(6) : "--")
        color: "#5D6D7E"
        font { pixelSize: 11; family: "monospace" }
        anchors.verticalCenter: parent.verticalCenter
    }
    Text {
        text: "UPD: " + root.lastUpdate
        color: "#5D6D7E"
        font { pixelSize: 11; family: "monospace" }
        anchors.verticalCenter: parent.verticalCenter
    }
}
