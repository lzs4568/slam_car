"""
遥控控制: 键盘操控小车，发布 /cmd_vel
(后续可切换为手柄 yahboom_joy_X3)
"""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():

    keyboard_ctrl = Node(
        package='yahboomcar_ctrl',
        executable='yahboom_keyboard',
        name='keyboard_ctrl',
        output='screen',
        emulate_tty=True,
        remappings=[('/cmd_vel', '/cmd_vel_raw')],
    )

    return LaunchDescription([keyboard_ctrl])
