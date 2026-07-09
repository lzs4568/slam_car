"""
发布机器人模型 URDF (robot_description) + 可选 RViz 可视化
用法: ros2 launch slam_car_bringup robot_description.launch.py
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('slam_car_bringup')

    # URDF
    urdf_path = os.path.join(pkg_share, 'urdf', 'slam_car_bringup.urdf')
    with open(urdf_path, 'r') as f:
        robot_desc = f.read()

    # Args
    rviz_arg = DeclareLaunchArgument(
        'rviz', default_value='false',
        description='是否启动 RViz2')
    gui_arg = DeclareLaunchArgument(
        'gui', default_value='false',
        description='是否启动 joint_state_publisher_gui')

    # robot_state_publisher — 唯一发布 /robot_description 和 basefoot_link→base_link→...
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        parameters=[{'robot_description': robot_desc}],
    )

    # joint_state_publisher_gui
    joint_state_publisher_gui = Node(
        package='joint_state_publisher_gui',
        executable='joint_state_publisher_gui',
        name='joint_state_publisher_gui',
        condition=IfCondition(LaunchConfiguration('gui')),
    )

    # RViz2
    rviz_config = os.path.join(pkg_share, 'rviz', 'urdf.rviz')
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config, '-f', 'base_link'],
        condition=IfCondition(LaunchConfiguration('rviz')),
    )

    return LaunchDescription([
        rviz_arg,
        gui_arg,
        robot_state_publisher,
        joint_state_publisher_gui,
        rviz_node,
    ])
