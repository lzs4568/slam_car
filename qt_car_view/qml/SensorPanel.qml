import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 明亮工业风 — 传感器面板
Rectangle {
    id: root
    color: "#BCC4CC"

    property var sensorData: ({})
    property var alarms: ({})

    readonly property var sensorConfig: [
        { name: "温度 TEMP",        key: "temp",            unit: "°C",    color: "#E67E22" },
        { name: "湿度 HUM",         key: "hum",             unit: "%",     color: "#2980B9" },
        { name: "MQ2 可燃气体",     key: "mq2_gas_value",   unit: "",      color: "#C0392B" },
        { name: "MQ135 空气质量",   key: "mq135_gas_value", unit: "",      color: "#8E44AD" },
        { name: "PM2.5 颗粒物",     key: "pm2_5",           unit: "ug/m3", color: "#5D6D7E" },
        { name: "eCO2 二氧化碳",    key: "eco2",            unit: "ppm",   color: "#16A085" },
        { name: "TVOC 有机物",      key: "tvoc",            unit: "ppb",   color: "#D35400" },
        { name: "volt",             key: "volt",            unit: "V",     color: "#1E8449" }
    ]

    // 面板标题栏
    Rectangle {
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 28
        color: "#6B7B8B"
        Text {
            anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
            text: "SENSOR DATA"
            color: "#F0F2F4"
            font { pixelSize: 12; bold: true; family: "monospace" }
        }
        // 状态指示灯组
        Row {
            anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
            spacing: 6
            Repeater {
                model: 3
                Rectangle {
                    width: 6; height: 6; radius: 3
                    color: "#4CAF50"
                }
            }
        }
    }

    Column {
        anchors {
            left: parent.left; right: parent.right; top: parent.top; topMargin: 30
        }
        spacing: 8.8 //卡片间距

        Repeater {
            model: root.sensorConfig

            SensorCard {
                width: parent.width
                sensorName: modelData.name
                sensorUnit: modelData.unit
                sensorKey: modelData.key
                accentColor: modelData.color
                value: root.sensorData[modelData.key] !== undefined
                       ? root.sensorData[modelData.key] : 0
                hasData: root.sensorData[modelData.key] !== undefined
                alarmActive: root.alarms[modelData.key] !== undefined
            }
        }
    }
}
