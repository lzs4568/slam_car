"""
UM960 RTK-GPS 启动: 解析NMEA输出，发布 /gps/fix (NavSatFix)
用法: ros2 launch slam_car_bringup car_gps.launch.py
"""
from launch import LaunchDescription
from launch.actions import SetEnvironmentVariable
from launch.substitutions import EnvironmentVariable
from launch_ros.actions import Node


def generate_launch_description():
    # 优先使用系统 numpy (避免 ~/.local 的 numpy 2.x 破坏 nmea_navsat_driver)
    system_python_path = '/usr/lib/python3/dist-packages'

    nmea_driver = Node(
        package='nmea_navsat_driver',
        executable='nmea_serial_driver',
        name='nmea_serial_driver',
        output='screen',
        parameters=[{
            'port': '/dev/gps_4g',
            'baud': 115200,
            'frame_id': 'gps_link',
            'time_ref_source': 'gps',
            'useRMC': False,
        }],
        remappings=[
            ('/fix', '/gps/fix'),
            ('/heading', '/gps/heading'),
            ('/vel', '/gps/vel'),
            ('/time_reference', '/gps/time_reference'),
        ],
    )

    return LaunchDescription([
        SetEnvironmentVariable('PYTHONPATH', [system_python_path, ':', EnvironmentVariable('PYTHONPATH', default_value='')]),
        nmea_driver,
    ])
