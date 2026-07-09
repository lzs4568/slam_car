"""
Nav2 导航启动: 在线建图导航 / 离线地图导航
用法:
  在线: ros2 launch slam_car_bringup car_nav2.launch.py
  离线: ros2 launch slam_car_bringup car_nav2.launch.py nav_mode:=offline map:=~/data/map/car_map.yaml
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('slam_car_bringup')

    # Args
    nav_mode = LaunchConfiguration('nav_mode')
    nav_mode_arg = DeclareLaunchArgument(
        'nav_mode', default_value='online',
        description='online=RTAB-Map实时地图 | offline=加载静态地图+AMCL')
    map_path = LaunchConfiguration('map')
    map_arg = DeclareLaunchArgument(
        'map', default_value='/home/elf/data/map/car_map.yaml',
        description='离线模式地图路径 (绝对路径)')

    params_file = os.path.join(pkg_share, 'config', 'nav2_params.yaml')

    # 在线模式: map topic 指向 RTAB-Map grid_map
    # 离线模式: map topic 指向 map_server 发布的 /map
    map_topic = PythonExpression([
        "'/rtabmap/grid_map' if '", nav_mode, "' == 'online' else '/map'"
    ])

    # Map Server (离线模式)
    map_server = Node(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        output='screen',
        parameters=[params_file, {'yaml_filename': map_path}],
        condition=IfCondition(PythonExpression([
            "'", nav_mode, "' == 'offline'"
        ])),
    )

    # AMCL (离线模式)
    amcl = Node(
        package='nav2_amcl',
        executable='amcl',
        name='amcl',
        output='screen',
        parameters=[params_file],
        remappings=[('scan', '/scan')],
        condition=IfCondition(PythonExpression([
            "'", nav_mode, "' == 'offline'"
        ])),
    )

    # 在线模式: RTAB-Map 发 /rtabmap/grid_map, 转发到 /map 供 global_costmap static_layer
    map_relay = Node(
        package='topic_tools',
        executable='relay',
        name='map_relay',
        output='screen',
        arguments=['/rtabmap/grid_map', '/map'],
        condition=IfCondition(PythonExpression([
            "'", nav_mode, "' == 'online'"
        ])),
    )

    # Lifecycle Manager — node_names 根据模式动态决定
    lifecycle_node_names_online = PythonExpression([
        "['controller_server','planner_server','bt_navigator'] if '",
        nav_mode, "' == 'online' else ",
        "['controller_server','planner_server','bt_navigator','map_server','amcl']"
    ])
    lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_navigation',
        output='screen',
        parameters=[{
            'autostart': True,
            'node_names': lifecycle_node_names_online,
        }],
    )

    # Nav2 核心节点 (在线/离线共用)
    controller_server = Node(
        package='nav2_controller',
        executable='controller_server',
        name='controller_server',
        output='screen',
        parameters=[params_file],
        remappings=[('cmd_vel', '/cmd_vel_raw')],
    )

    planner_server = Node(
        package='nav2_planner',
        executable='planner_server',
        name='planner_server',
        output='screen',
        parameters=[params_file],
        remappings=[('map', map_topic)],
    )

    bt_navigator = Node(
        package='nav2_bt_navigator',
        executable='bt_navigator',
        name='bt_navigator',
        output='screen',
        parameters=[params_file],
    )

    return LaunchDescription([
        nav_mode_arg,
        map_arg,
        map_server,
        amcl,
        map_relay,
        lifecycle_manager,
        controller_server,
        planner_server,
        bt_navigator,
    ])
