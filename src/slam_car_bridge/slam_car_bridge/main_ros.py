#!/usr/bin/env python3
"""
语音 + ROS2 组合启动入口
=======================
同时跑 VoicePipeline (语音管线, 来自 elf2_bridge) 和 ROS2 节点 (标注 + 语音桥接)

用法:
  # 先启动底盘+导航:
  ros2 launch slam_car_bringup bringup_all.launch.py
  ros2 launch slam_car_bringup car_nav2.launch.py

  # 再启动语音桥接:
  ros2 launch slam_car_bridge voice_bridge.launch.py

  # 或直接运行本脚本:
  python3 main_ros.py [--port /dev/ttyACM0] [--api-key sk-xxx]
"""

import os
import sys
import glob
import argparse
import signal
import logging
import threading

# ---- 找到 elf2_bridge 路径 ----
_ELF2_BRIDGE_PATHS = [
    os.path.expanduser("~/elf2_bridge"),
    os.path.expanduser("~/data/elf2_bridge"),
    "/data/elf2_bridge",
]
for _p in _ELF2_BRIDGE_PATHS:
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
# ~/.local 可能有 dashscope/pyserial 包
sys.path.insert(0, os.path.expanduser("~/.local/lib/python3.10/site-packages"))

import rclpy
from rclpy.executors import MultiThreadedExecutor

from slam_car_bridge.annotation_node import AnnotationNode
from slam_car_bridge.ros2_voice_bridge import Ros2VoiceBridge
from slam_car_bridge.voice_chat_bridge import VoiceChatBridge

logger = logging.getLogger("main_ros")


def find_audio_port() -> str:
    if os.path.exists("/dev/esp32_audio"):
        return "/dev/esp32_audio"
    for pat in ["/dev/ttyACM*", "/dev/ttyUSB*"]:
        ports = sorted(glob.glob(pat))
        if ports:
            acm = [p for p in ports if "ACM" in p]
            return acm[0] if acm else ports[0]
    raise FileNotFoundError("未找到串口设备！请确认 ESP32 USB 已插入")


def main():
    parser = argparse.ArgumentParser(description="语音+ROS2 组合启动")
    parser.add_argument("--port", "-p", default=None,
                        help="音频串口路径 (默认自动检测)")
    parser.add_argument("--api-key", default=None,
                        help="DashScope API Key (默认读环境变量)")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # ---- API Key ----
    api_key = args.api_key or os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print("❌ 请设置 DASHSCOPE_API_KEY")
        sys.exit(1)

    # ---- 串口 ----
    port = args.port or find_audio_port()

    # ---- 加载 elf2_bridge pipeline ----
    try:
        from pipeline import VoicePipeline
    except ImportError:
        print("❌ 找不到 elf2_bridge/pipeline.py")
        print(f"   sys.path: {sys.path[:5]}")
        print("   请将 elf2_bridge 目录加入 PYTHONPATH")
        sys.exit(1)

    # ---- 启动语音管线 ----
    pipeline = VoicePipeline(port, api_key)
    bus, cloud, player = pipeline.get_components()

    # ---- 启动 ROS2 节点 ----
    rclpy.init(args=None)
    annotation = AnnotationNode()
    bridge = Ros2VoiceBridge(bus, cloud, player)
    chat_bridge = VoiceChatBridge(pipeline, bus)

    executor = MultiThreadedExecutor()
    executor.add_node(annotation)
    executor.add_node(bridge)
    executor.add_node(chat_bridge)

    ros_thread = threading.Thread(target=executor.spin, daemon=True)
    ros_thread.start()

    # ---- 退出处理 ----
    _shutdown_called = False

    def shutdown(sig=None, frame=None):
        nonlocal _shutdown_called
        if _shutdown_called:
            return
        _shutdown_called = True
        logger.info("收到退出信号...")
        pipeline.stop()
        executor.shutdown()
        try:
            rclpy.shutdown()
        except Exception:
            pass

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("=" * 50)
    print(f"🎤 音频串口: {port}")
    print("🤖 语音桥接 + 语义标注 已启动")
    print()
    print("语音指令:")
    print("  '这里是<地名>'    → 标注地点")
    print("  '去<地名>'        → 自主导航")
    print("  '前进/后退/左转/右转/停车' → 手动移动")
    print()
    print("RViz2 标注:")
    print("  笔记本 rviz2 → Publish Point → 点击地图 → 自动记录")
    print()
    print("等待 ESP32 唤醒词 '小隆小隆'...")
    print("=" * 50)

    pipeline.run()
    shutdown()


if __name__ == "__main__":
    main()
