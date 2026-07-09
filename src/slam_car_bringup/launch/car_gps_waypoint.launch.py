"""
GPS 航点接收: 将经纬度目标转为 map 帧 goal_pose 发给 Nav2
用法:
  ros2 launch slam_car_bringup car_gps_waypoint.launch.py
  ros2 launch slam_car_bringup car_gps_waypoint.launch.py datum_lat:=31.2 datum_lon:=121.4
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    datum_lat_arg = DeclareLaunchArgument(
        'datum_lat', default_value='0.0',
        description='参考原点纬度 (0=从/gps/fix自动获取)')
    datum_lon_arg = DeclareLaunchArgument(
        'datum_lon', default_value='0.0',
        description='参考原点经度 (0=从/gps/fix自动获取)')

    gps_waypoint_node = Node(
        package='slam_car_bringup',
        executable='gps_waypoint',
        name='gps_waypoint',
        output='screen',
        parameters=[{
            'datum_lat': LaunchConfiguration('datum_lat'),
            'datum_lon': LaunchConfiguration('datum_lon'),
        }],
    )

    return LaunchDescription([
        datum_lat_arg,
        datum_lon_arg,
        gps_waypoint_node,
    ])
