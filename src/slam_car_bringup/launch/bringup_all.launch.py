"""
一键启动: 底盘 + SLAM
用法: ros2 launch slam_car_bringup bringup_all.launch.py [delete_db_on_start:=true] [use_gps:=true]
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    pkg_share = get_package_share_directory('slam_car_bringup')

    # SLAM 参数透传
    delete_db_arg = DeclareLaunchArgument(
        'delete_db_on_start', default_value='false',
        description='启动时删除旧数据库从头建图')
    localization_arg = DeclareLaunchArgument(
        'localization', default_value='false',
        description='纯定位模式 (不建图)')
    db_path_arg = DeclareLaunchArgument(
        'database_path', default_value='~/data/map/rtabmap.db',
        description='RTAB-Map数据库路径')
    use_gps_arg = DeclareLaunchArgument(
        'use_gps', default_value='false',
        description='启用RTK-GPS约束')

    chassis = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(pkg_share, 'launch', 'car_chassis.launch.py')
        ]),
    )

    slam = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(pkg_share, 'launch', 'car_slam.launch.py')
        ]),
        launch_arguments={
            'delete_db_on_start': LaunchConfiguration('delete_db_on_start'),
            'localization': LaunchConfiguration('localization'),
            'database_path': LaunchConfiguration('database_path'),
            'use_gps': LaunchConfiguration('use_gps'),
        }.items(),
    )

    return LaunchDescription([
        delete_db_arg,
        localization_arg,
        db_path_arg,
        use_gps_arg,
        chassis,
        slam,
    ])
