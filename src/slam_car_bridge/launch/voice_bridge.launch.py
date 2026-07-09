#!/usr/bin/env python3
"""
语音桥接启动: annotation_node + ros2_voice_bridge
=================================================
需要先启动底盘+SLAM+Nav2 (bringup_all + car_nav2)

前置条件:
  ESP32 USB 已插入 ELF2
  DASHSCOPE_API_KEY 环境变量已设 (或 launch 时传参)
  /data/elf2_bridge/pipeline.py 已部署

用法:
  ros2 launch slam_car_bridge voice_bridge.launch.py
  ros2 launch slam_car_bridge voice_bridge.launch.py audio_port:=/dev/ttyACM0
"""

import os
import sys

# 将 elf2_bridge 路径加入 PYTHONPATH, 让 ros2_voice_bridge 能 import pipeline
# 放在 os.environ 里确保 launch 的子进程继承
def _add_elf2_bridge_path():
    candidates = [
        os.path.expanduser("~/elf2_bridge"),
        os.path.expanduser("~/data/elf2_bridge"),
        "/data/elf2_bridge",
    ]
    for p in candidates:
        p = os.path.abspath(os.path.expanduser(p))
        if os.path.isdir(p):
            env = os.environ.copy()
            pythonpath = env.get("PYTHONPATH", "")
            if p not in pythonpath:
                env["PYTHONPATH"] = f"{p}:{pythonpath}" if pythonpath else p
            return env
    return os.environ

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    env = _add_elf2_bridge_path()

    # ---- args ----
    audio_port_arg = DeclareLaunchArgument(
        "audio_port", default_value="/dev/ttyACM0",
        description="ESP32 USB CDC 音频串口")

    api_key_arg = DeclareLaunchArgument(
        "api_key",
        default_value=os.environ.get("DASHSCOPE_API_KEY", ""),
        description="DashScope API Key")

    # ---- 节点 ----
    # 标注节点: 独立, 不依赖 pipeline
    annotation_node = Node(
        package="slam_car_bridge",
        executable="annotation_node",
        name="annotation_node",
        output="screen",
    )

    # 语音桥接节点: import pipeline (需要 PYTHONPATH 包含 elf2_bridge)
    # 注: ros2_voice_bridge 独立运行时不连 pipeline (bus/cloud/player 为 None)
    # 如需完整语音→ROS2 功能, 使用 main_ros.py 组合启动
    voice_bridge_node = Node(
        package="slam_car_bridge",
        executable="ros2_voice_bridge",
        name="ros2_voice_bridge",
        output="screen",
    )

    return LaunchDescription([
        audio_port_arg,
        api_key_arg,
        annotation_node,
        voice_bridge_node,
    ])
