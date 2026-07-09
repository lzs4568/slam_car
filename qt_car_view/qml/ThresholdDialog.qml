import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Dialog {
    id: root
    title: "传感器阈值设置"
    modal: true
    standardButtons: Dialog.Ok | Dialog.Cancel | Dialog.Reset
    width: 400

    property var dataMgr: null

    function loadThresholds() {
        var t = dataMgr.getThresholds()
        tempHighSpin.value = t.temp_high || 60
        tempLowSpin.value = t.temp_low || 0
        humHighSpin.value = t.hum_high || 95
        humLowSpin.value = t.hum_low || 0
        mq2HighSpin.value = t.mq2_gas_value_high || 500
        mq135HighSpin.value = t.mq135_gas_value_high || 500
        pm25HighSpin.value = t.pm2_5_high || 75
        batHighSpin.value = t.battery_high || 13
        batLowSpin.value = t.battery_low || 10.5
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        GroupBox { title: "温度 (temp)"
            Layout.fillWidth: true
            RowLayout {
                Text { text: "上限(°C):"; Layout.preferredWidth: 100 }
                SpinBox { id: tempHighSpin; from: 0; to: 150; editable: true }
                Text { text: "下限(°C):"; Layout.preferredWidth: 100 }
                SpinBox { id: tempLowSpin; from: -50; to: 100; editable: true }
            }
        }
        GroupBox { title: "湿度 (hum)"
            Layout.fillWidth: true
            RowLayout {
                Text { text: "上限(%):"; Layout.preferredWidth: 100 }
                SpinBox { id: humHighSpin; from: 0; to: 100; editable: true }
                Text { text: "下限(%):"; Layout.preferredWidth: 100 }
                SpinBox { id: humLowSpin; from: 0; to: 100; editable: true }
            }
        }
        GroupBox { title: "MQ2 可燃气体"
            Layout.fillWidth: true
            RowLayout { Text { text: "上限:"; Layout.preferredWidth: 100 }
                SpinBox { id: mq2HighSpin; from: 0; to: 4095; editable: true } }
        }
        GroupBox { title: "MQ135 空气质量"
            Layout.fillWidth: true
            RowLayout { Text { text: "上限:"; Layout.preferredWidth: 100 }
                SpinBox { id: mq135HighSpin; from: 0; to: 4095; editable: true } }
        }
        GroupBox { title: "PM2.5"
            Layout.fillWidth: true
            RowLayout { Text { text: "上限(μg/m³):"; Layout.preferredWidth: 100 }
                SpinBox { id: pm25HighSpin; from: 0; to: 999; editable: true } }
        }
        GroupBox { title: "电池电压 (battery)"
            Layout.fillWidth: true
            RowLayout {
                Text { text: "上限(V):"; Layout.preferredWidth: 100 }
                SpinBox { id: batHighSpin; from: 0; to: 20; editable: true }
                Text { text: "下限(V):"; Layout.preferredWidth: 100 }
                SpinBox { id: batLowSpin; from: 0; to: 20; editable: true }
            }
        }
    }

    onReset: {
        tempHighSpin.value = 60; tempLowSpin.value = 0
        humHighSpin.value = 95; humLowSpin.value = 0
        mq2HighSpin.value = 500; mq135HighSpin.value = 500
        pm25HighSpin.value = 75; batHighSpin.value = 13; batLowSpin.value = 10.5
    }

    onAccepted: {
        var thresholds = {
            temp_high: tempHighSpin.value, temp_low: tempLowSpin.value,
            hum_high: humHighSpin.value, hum_low: humLowSpin.value,
            mq2_gas_value_high: mq2HighSpin.value,
            mq135_gas_value_high: mq135HighSpin.value,
            pm2_5_high: pm25HighSpin.value,
            battery_high: batHighSpin.value, battery_low: batLowSpin.value
        }
        dataMgr.setThresholds(thresholds)
    }
}
