import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// 语音对话框 — 显示 ASR/LLM 对话 + 打字发送
Rectangle {
    id: root
    color: "#BCC4CC"

    property int maxMessages: 200

    // 外部调用：追加一条消息气泡
    function appendMessage(role, text) {
        if (!text || text.length === 0)
            return
        chatModel.append({ "role": role, "text": text })
        while (chatModel.count > root.maxMessages)
            chatModel.remove(0)
        chatList.positionViewAtEnd()
    }

    function sendCurrent() {
        var t = inputField.text.trim()
        if (t.length === 0)
            return
        if (typeof ros2Bridge !== "undefined" && ros2Bridge)
            ros2Bridge.sendChatInput(t)
        inputField.text = ""
        // 不本地追加气泡：靠后端 /voice/chat 回显 (role=user)
    }

    // 标题栏
    Rectangle {
        id: titleBar
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 28
        color: "#6B7B8B"
        Text {
            anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
            text: "语音对话"
            color: "#F0F2F4"
            font { pixelSize: 12; bold: true; family: "monospace" }
        }
    }

    ListModel { id: chatModel }

    ListView {
        id: chatList
        anchors {
            left: parent.left; right: parent.right
            top: titleBar.bottom; bottom: inputRow.top
            margins: 6
        }
        clip: true
        spacing: 6
        model: chatModel
        boundsBehavior: Flickable.StopAtBounds

        delegate: Item {
            width: chatList.width
            height: bubble.height + 2

            Rectangle {
                id: bubble
                anchors.right: model.role === "user" ? parent.right : undefined
                anchors.left: model.role === "user" ? undefined : parent.left
                // 气泡尺寸跟随文本，文本宽度绑定到 chatList（不依赖 bubble，避免循环）
                width: bubbleText.width + 14
                height: bubbleText.height + 14
                radius: 8
                color: model.role === "user" ? "#6FAE6F" : "#3D5A80"

                Text {
                    id: bubbleText
                    x: 7; y: 7
                    width: Math.min(implicitWidth, chatList.width * 0.85 - 14)
                    text: model.text
                    color: "#FFFFFF"
                    wrapMode: Text.Wrap
                    font { pixelSize: 12; family: "monospace" }
                }
            }
        }
    }

    // 输入栏
    RowLayout {
        id: inputRow
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 6 }
        spacing: 6

        TextField {
            id: inputField
            Layout.fillWidth: true
            placeholderText: "输入消息…"
            font { pixelSize: 12; family: "monospace" }
            onAccepted: root.sendCurrent()
        }

        Button {
            text: "发送"
            font { pixelSize: 12; bold: true; family: "monospace" }
            onClicked: root.sendCurrent()
        }
    }
}
