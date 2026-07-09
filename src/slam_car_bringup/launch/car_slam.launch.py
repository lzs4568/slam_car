"""
SLAM启动: LiDAR + RGB-D相机 + RTAB-Map
需要先启动 car_chassis 提供 odom tf
用法:
  ros2 launch slam_car_bringup car_slam.launch.py
  ros2 launch slam_car_bringup car_slam.launch.py use_gps:=true delete_db_on_start:=true
  ros2 launch slam_car_bringup car_slam.launch.py launch_camera:=false  # 相机已单独启动时
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression


def generate_launch_description():
    pkg_share = get_package_share_directory('slam_car_bringup')

    # Args
    localization_arg = DeclareLaunchArgument(
        'localization', default_value='false',
        description='纯定位模式 (不建图)')
    delete_db_arg = DeclareLaunchArgument(
        'delete_db_on_start', default_value='false',
        description='启动时删除旧数据库从头建图')
    db_path_arg = DeclareLaunchArgument(
        'database_path', default_value='~/data/map/rtabmap.db',
        description='RTAB-Map数据库路径')
    use_gps_arg = DeclareLaunchArgument(
        'use_gps', default_value='false',
        description='启用RTK-GPS约束 (需先连接UM960)')
    launch_camera_arg = DeclareLaunchArgument(
        'launch_camera', default_value='true',
        description='是否在此 launch 中启动相机 (若已单独启动相机则设为 false)')

    # YDLidar
    ydlidar = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(pkg_share, 'launch', 'ydlidar.launch.py')
        ]),
    )

    # 优化版相机 launch (component_container_mt + 10fps，避免单线程阻塞卡死)
    orbbec_camera = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(pkg_share, 'launch', 'camera.launch.py')
        ]),
        condition=IfCondition(PythonExpression([
            "'", LaunchConfiguration('launch_camera'), "' == 'true'"
        ])),
    )

    # RTK-GPS
    gps = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(pkg_share, 'launch', 'car_gps.launch.py')
        ]),
    )

    # RTAB-Map SLAM
    rtabmap = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(pkg_share, 'launch', 'rtabmap.launch.py')
        ]),
        launch_arguments={
            'database_path': LaunchConfiguration('database_path'),
            'delete_db_on_start': LaunchConfiguration('delete_db_on_start'),
            'localization': LaunchConfiguration('localization'),
            'use_gps': LaunchConfiguration('use_gps'),
        }.items(),
    )

    return LaunchDescription([
        localization_arg,
        delete_db_arg,
        db_path_arg,
        use_gps_arg,
        launch_camera_arg,
        ydlidar,
        orbbec_camera,
        gps,
        rtabmap,
    ])
