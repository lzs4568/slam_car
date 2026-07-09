import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Dialog {
    id: root
    title: "连接配置"
    modal: true
    standardButtons: Dialog.Ok | Dialog.Cancel
    width: 500

    property var cfgManager: null

    function loadConfig() {
        var cfg = cfgManager.loadConnectionConfig()
        if (Object.keys(cfg).length === 0) {
            hostField.text = "7aaaf6c8f5.st1.iotda-app.cn-east-3.myhuaweicloud.com"
            portSpin.value = 8883
        } else {
            accessKeyField.text = cfg.mqtt_access_key || ""
            accessCodeField.text = cfg.mqtt_access_code || ""
            instanceIdField.text = cfg.mqtt_instance_id || ""
            hostField.text = cfg.mqtt_host || ""
            portSpin.value = cfg.mqtt_port || 8883
            apiKeyField.text = cfg.amap_api_key || ""
            gpsTopicField.text = cfg.ros2_gps_topic || "/gps/fix"
            waypointTopicField.text = cfg.ros2_waypoint_topic || "/gps_waypoint"
            streamUrlField.text = cfg.stream_url || "http://192.168.5.10:8082"
            elfHostField.text = cfg.elf_host || "192.168.5.10"
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        GroupBox { title: "华为云 IoT MQTT"
            Layout.fillWidth: true
            ColumnLayout {
                RowLayout { Text { text: "Access Key:"; Layout.preferredWidth: 120 }
                    TextField { id: accessKeyField; echoMode: TextInput.Normal; Layout.fillWidth: true } }
                RowLayout { Text { text: "Access Code:"; Layout.preferredWidth: 120 }
                    TextField { id: accessCodeField; echoMode: TextInput.Normal; Layout.fillWidth: true } }
                RowLayout { Text { text: "Instance ID:"; Layout.preferredWidth: 120 }
                    TextField { id: instanceIdField; Layout.fillWidth: true } }
                RowLayout { Text { text: "MQTT Host:"; Layout.preferredWidth: 120 }
                    TextField { id: hostField; Layout.fillWidth: true } }
                RowLayout { Text { text: "MQTT Port:"; Layout.preferredWidth: 120 }
                    SpinBox { id: portSpin; from: 1; to: 65535 } }
            }
        }

        GroupBox { title: "高德地图"
            Layout.fillWidth: true
            RowLayout {
                Text { text: "API Key:"; Layout.preferredWidth: 120 }
                TextField { id: apiKeyField; Layout.fillWidth: true }
            }
        }

        GroupBox { title: "ROS2"
            Layout.fillWidth: true
            ColumnLayout {
                RowLayout { Text { text: "GPS 话题:"; Layout.preferredWidth: 120 }
                    TextField { id: gpsTopicField; Layout.fillWidth: true } }
                RowLayout { Text { text: "目标点话题:"; Layout.preferredWidth: 120 }
                    TextField { id: waypointTopicField; Layout.fillWidth: true } }
            }
        }

        GroupBox { title: "视频流 & 小车地址"
            Layout.fillWidth: true
            ColumnLayout {
                RowLayout {
                    Text { text: "ELF2 IP/主机名:"; Layout.preferredWidth: 120 }
                    TextField { id: elfHostField; placeholderText: "192.168.5.10 或 elf2.local"; Layout.fillWidth: true }
                    Text {
                        text: "⚠ IP 变时改这里"
                        color: "#E67E22"
                        font { pixelSize: 10; family: "monospace" }
                    }
                }
                RowLayout {
                    Text { text: "MJPEG 流地址:"; Layout.preferredWidth: 120 }
                    TextField { id: streamUrlField; placeholderText: "http://192.168.5.10:8082"; Layout.fillWidth: true }
                    Text {
                        text: "备用"
                        color: "#9098A0"
                        font { pixelSize: 10; family: "monospace" }
                    }
                }
                Text {
                    text: "ROS2 自动发现 (无需配置IP)  |  TCP H.264: tcp://" + elfHostField.text + ":8554"
                    color: "#7B8B9B"
                    font { pixelSize: 10; family: "monospace" }
                    Layout.fillWidth: true
                }
            }
        }
    }

    onAccepted: {
        var config = {
            mqtt_access_key: accessKeyField.text,
            mqtt_access_code: accessCodeField.text,
            mqtt_instance_id: instanceIdField.text,
            mqtt_host: hostField.text,
            mqtt_port: portSpin.value,
            amap_api_key: apiKeyField.text,
            ros2_gps_topic: gpsTopicField.text,
            ros2_waypoint_topic: waypointTopicField.text,
            stream_url: streamUrlField.text,
            elf_host: elfHostField.text
        }
        cfgManager.saveConnectionConfig(config)
    }
}
