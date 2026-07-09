"""
底盘启动: 驱动 + 里程计 + IMU滤波 + EKF融合
输出: odom->base_footprint tf, /odom topic
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('slam_car_bringup')

    # Args
    pub_odom_tf_arg = DeclareLaunchArgument(
        'pub_odom_tf', default_value='false',
        description='base_node是否发布odom->base_footprint tf (EKF模式由EKF发布)')
    wheelbase_arg = DeclareLaunchArgument(
        'wheelbase', default_value='0.25',
        description='轮距 (m)')

    # robot_state_publisher 由 robot_description.launch.py 统一管理
    robot_model = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(pkg_share, 'launch', 'robot_description.launch.py')
        ]),
        launch_arguments={'rviz': 'false', 'gui': 'false'}.items(),
    )

    # 速度缩放 — 订阅 /cmd_vel_raw, 乘系数后发布 /cmd_vel
    vel_scaler = Node(
        package='slam_car_bringup',
        executable='vel_scaler_node',
        name='vel_scaler',
        parameters=[{
            'angular_scale': 2.0,
            'linear_scale': 1.0,
        }],
    )

    # 底盘驱动 — 与STM32通信，发布 /vel_raw, /imu/data_raw
    driver = Node(
        package='yahboomcar_bringup',
        executable='Mcnamu_driver_x1',
        name='driver_node',
    )

    # 里程计 — 订阅 /vel_raw，发布 /odom_raw
    base_node = Node(
        package='yahboomcar_base_node',
        executable='base_node_x1',
        name='base_node',
        parameters=[{
            'pub_odom_tf': LaunchConfiguration('pub_odom_tf'),
            'wheelbase': LaunchConfiguration('wheelbase'),
        }],
    )

    # IMU滤波 — /imu/data_raw → /imu/data
    imu_filter = Node(
        package='imu_filter_madgwick',
        executable='imu_filter_madgwick_node',
        name='imu_filter_madgwick',
        parameters=[{
            'fixed_frame': 'base_link',
            'use_mag': False,
            'publish_tf': False,
            'world_frame': 'enu',
            'orientation_stddev': 0.05,
        }],
    )

    # 打滑检测 — 对比 IMU/odom, 打滑时膨胀协方差 → /odom_corrected
    slip_detector = Node(
        package='slam_car_bringup',
        executable='slip_detector',
        name='slip_detector',
        parameters=[{
            'slip_threshold': 0.3,
            'cov_scale_max': 1000.0,
        }],
    )

    # EKF融合 — /odom_corrected + /imu/data → odom→base_footprint tf, /odom
    ekf = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        parameters=[os.path.join(pkg_share, 'config', 'ekf.yaml')],
    )

    return LaunchDescription([
        pub_odom_tf_arg,
        wheelbase_arg,
        robot_model,
        vel_scaler,
        driver,
        base_node,
        imu_filter,
        slip_detector,
        ekf,
    ])
