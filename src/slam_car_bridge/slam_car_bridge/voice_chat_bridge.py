#!/usr/bin/env python3
"""
语音对话中继节点
================
把语音管线的对话 (ASR + LLM 回复) 转发到 ROS2, 供前端对话框显示;
并接收前端打字的文本, 注入语音管线 (与语音相同路径: 指令匹配 + LLM + TTS)。

话题:
  发布 /voice/chat        (std_msgs/String, JSON {role, text, ts})
  订阅 /voice/chat_input  (std_msgs/String, 纯文本)

由 main_ros.py 构造并传入 pipeline + voice_bus。
"""

import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


def build_chat_payload(role: str, text: str, ts: float) -> str:
    """构造 /voice/chat 的 JSON 字符串 (纯函数, 便于单测)"""
    return json.dumps(
        {"role": role, "text": text, "ts": int(ts)},
        ensure_ascii=False,
    )


class VoiceChatBridge(Node):
    def __init__(self, pipeline=None, voice_bus=None):
        super().__init__('voice_chat_bridge')

        self._pipeline = pipeline

        self._chat_pub = self.create_publisher(String, '/voice/chat', 10)
        self._input_sub = self.create_subscription(
            String, '/voice/chat_input', self._on_chat_input, 10)

        if voice_bus is not None:
            voice_bus.on_asr(lambda text: self._publish_chat('user', text))
            voice_bus.on_llm(lambda text: self._publish_chat('assistant', text))
            self.get_logger().info("对话中继就绪 (已挂 on_asr/on_llm)")
        else:
            self.get_logger().warn("voice_bus 为空, 对话中继仅接收打字输入")

    def _publish_chat(self, role: str, text: str):
        msg = String()
        msg.data = build_chat_payload(role, text, time.time())
        self._chat_pub.publish(msg)

    def _on_chat_input(self, msg: String):
        text = msg.data.strip()
        if not text:
            return
        self.get_logger().info(f"打字输入: {text}")
        if self._pipeline is not None:
            self._pipeline.inject_text(text)
        else:
            self.get_logger().warn("pipeline 为空, 无法处理打字输入")


def main(args=None):
    """独立入口 (烟雾测试用, 不连 pipeline/bus)"""
    rclpy.init(args=args)
    node = VoiceChatBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
