#!/usr/bin/env python3
"""启动 YOLO 推理节点的 launch 文件。

用法:
  ros2 launch slam_car_yolo yolo.launch.py
  ros2 launch slam_car_yolo yolo.launch.py camera_topic:=/my_camera/image_raw

在 ELF2 上运行前需确保 LD_LIBRARY_PATH 能找到 librknnrt.so:
  export LD_LIBRARY_PATH=/data/yolov8/yolo_test/rknn-cpp-Multithreading-main/include:$LD_LIBRARY_PATH
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    model_path_arg = DeclareLaunchArgument(
        'model_path',
        default_value='/data/yolov8/car.rknn',
        description='RKNN 模型文件路径'
    )
    labels_path_arg = DeclareLaunchArgument(
        'labels_path',
        default_value='/data/yolov8/labels_list.txt',
        description='标签文件路径'
    )
    camera_topic_arg = DeclareLaunchArgument(
        'camera_topic',
        default_value='/camera/color/image_raw',
        description='RGB 图像话题名'
    )
    conf_threshold_arg = DeclareLaunchArgument(
        'conf_threshold',
        default_value='0.25',
        description='置信度阈值'
    )
    nms_threshold_arg = DeclareLaunchArgument(
        'nms_threshold',
        default_value='0.45',
        description='NMS IoU 阈值'
    )
    core_mask_arg = DeclareLaunchArgument(
        'core_mask',
        default_value='1',
        description='NPU 核心掩码 (1=Core0, 7=三核)'
    )

    yolo_node = Node(
        package='slam_car_yolo',
        executable='yolo_node',
        name='yolo_node',
        output='screen',
        parameters=[{
            'model_path': LaunchConfiguration('model_path'),
            'labels_path': LaunchConfiguration('labels_path'),
            'camera_topic': LaunchConfiguration('camera_topic'),
            'conf_threshold': LaunchConfiguration('conf_threshold'),
            'nms_threshold': LaunchConfiguration('nms_threshold'),
            'core_mask': LaunchConfiguration('core_mask'),
        }],
    )

    return LaunchDescription([
        model_path_arg,
        labels_path_arg,
        camera_topic_arg,
        conf_threshold_arg,
        nms_threshold_arg,
        core_mask_arg,
        yolo_node,
    ])
