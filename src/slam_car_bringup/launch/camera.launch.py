"""
优化版相机启动 (Orbbec Gemini 335L)
- 使用 component_container_mt (多线程) 代替 component_container (单线程)，避免阻塞卡死
- 默认 10fps，降低 CPU/带宽负载，SLAM 不需要 30fps
- 关闭 LDP/软滤波/加速度计/陀螺仪，省计算资源

用法:
  ros2 launch slam_car_bringup camera.launch.py
  ros2 launch slam_car_bringup camera.launch.py color_fps:=15 depth_fps:=15
"""
import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import PushRosNamespace, ComposableNodeContainer
from launch_ros.descriptions import ComposableNode


def generate_launch_description():
    # ============================================================
    # 性能关键参数（降低默认值以适配嵌入式板卡）
    # ============================================================
    fps_args = [
        DeclareLaunchArgument('color_fps',  default_value='10',
                              description='RGB 帧率 (默认10, 原厂30)'),
        DeclareLaunchArgument('depth_fps',  default_value='10',
                              description='深度帧率 (默认10, 原厂30)'),
    ]

    # ============================================================
    # 常规参数（透传原厂默认值）
    # ============================================================
    common_args = [
        DeclareLaunchArgument('camera_name', default_value='camera'),
        DeclareLaunchArgument('serial_number', default_value=''),
        DeclareLaunchArgument('usb_port', default_value=''),
        DeclareLaunchArgument('device_num', default_value='1'),
        DeclareLaunchArgument('connection_delay', default_value='100'),
        DeclareLaunchArgument('depth_registration', default_value='true'),
        DeclareLaunchArgument('use_intra_process', default_value='false'),

        # ---- RGB ----
        DeclareLaunchArgument('enable_color', default_value='true'),
        DeclareLaunchArgument('color_width',  default_value='424'),
        DeclareLaunchArgument('color_height', default_value='240'),
        DeclareLaunchArgument('color_format', default_value='MJPG'),
        DeclareLaunchArgument('color_qos', default_value='default'),
        DeclareLaunchArgument('color_camera_info_qos', default_value='default'),
        DeclareLaunchArgument('enable_color_auto_exposure', default_value='false'),
        DeclareLaunchArgument('color_exposure', default_value='10000'),
        DeclareLaunchArgument('color_gain', default_value='-1'),
        DeclareLaunchArgument('enable_color_auto_white_balance', default_value='true'),
        DeclareLaunchArgument('color_white_balance', default_value='-1'),

        # ---- 深度 ----
        DeclareLaunchArgument('enable_depth', default_value='true'),
        DeclareLaunchArgument('depth_width',  default_value='424'),
        DeclareLaunchArgument('depth_height', default_value='266'),
        DeclareLaunchArgument('depth_format', default_value='Y16'),
        DeclareLaunchArgument('depth_qos', default_value='default'),
        DeclareLaunchArgument('depth_camera_info_qos', default_value='default'),
        DeclareLaunchArgument('enable_depth_scale', default_value='true'),
        DeclareLaunchArgument('depth_precision', default_value='0'),

        # ---- 点云 (关闭，RTAB-Map 自己从深度图生成) ----
        DeclareLaunchArgument('enable_point_cloud', default_value='false'),
        DeclareLaunchArgument('enable_colored_point_cloud', default_value='false'),
        DeclareLaunchArgument('point_cloud_qos', default_value='default'),
        DeclareLaunchArgument('ordered_pc', default_value='false'),

        # ---- IR (关闭，用不上) ----
        DeclareLaunchArgument('enable_left_ir',  default_value='false'),
        DeclareLaunchArgument('enable_right_ir', default_value='false'),
        DeclareLaunchArgument('left_ir_width',  default_value='424'),
        DeclareLaunchArgument('left_ir_height', default_value='266'),
        DeclareLaunchArgument('left_ir_fps',    default_value='30'),
        DeclareLaunchArgument('left_ir_format', default_value='Y16'),
        DeclareLaunchArgument('left_ir_qos', default_value='default'),
        DeclareLaunchArgument('left_ir_camera_info_qos', default_value='default'),
        DeclareLaunchArgument('right_ir_width',  default_value='424'),
        DeclareLaunchArgument('right_ir_height', default_value='266'),
        DeclareLaunchArgument('right_ir_fps',    default_value='30'),
        DeclareLaunchArgument('right_ir_format', default_value='ANY'),
        DeclareLaunchArgument('right_ir_qos', default_value='default'),
        DeclareLaunchArgument('right_ir_camera_info_qos', default_value='default'),
        DeclareLaunchArgument('enable_ir_auto_exposure', default_value='false'),
        DeclareLaunchArgument('ir_exposure', default_value='3000'),
        DeclareLaunchArgument('ir_gain', default_value='-1'),

        # ---- IMU (关闭，底盘有自己的IMU) ----
        DeclareLaunchArgument('enable_sync_output_accel_gyro', default_value='false'),
        DeclareLaunchArgument('enable_accel', default_value='false'),
        DeclareLaunchArgument('enable_gyro',  default_value='false'),
        DeclareLaunchArgument('accel_rate',  default_value='200hz'),
        DeclareLaunchArgument('accel_range', default_value='4g'),
        DeclareLaunchArgument('gyro_rate',   default_value='200hz'),
        DeclareLaunchArgument('gyro_range',  default_value='1000dps'),
        DeclareLaunchArgument('liner_accel_cov', default_value='0.01'),
        DeclareLaunchArgument('angular_vel_cov', default_value='0.01'),

        # ---- TF ----
        DeclareLaunchArgument('publish_tf', default_value='true'),
        DeclareLaunchArgument('tf_publish_rate', default_value='10.0'),

        # ---- 硬件控制 ----
        DeclareLaunchArgument('enable_laser', default_value='true'),
        DeclareLaunchArgument('laser_on_off_mode', default_value='0'),
        DeclareLaunchArgument('laser_energy_level', default_value='50'),
        DeclareLaunchArgument('device_preset', default_value='High_Density'),

        # ---- 同步 ----
        DeclareLaunchArgument('sync_mode', default_value='true'),
        DeclareLaunchArgument('enable_frame_sync', default_value='true'),
        DeclareLaunchArgument('use_hardware_time', default_value='true'),
        DeclareLaunchArgument('depth_delay_us', default_value='0'),
        DeclareLaunchArgument('color_delay_us', default_value='0'),
        DeclareLaunchArgument('trigger2image_delay_us', default_value='0'),
        DeclareLaunchArgument('trigger_out_delay_us', default_value='0'),
        DeclareLaunchArgument('trigger_out_enabled', default_value='false'),

        # ---- 滤镜 (全关，省算力) ----
        DeclareLaunchArgument('enable_ldp', default_value='false'),
        DeclareLaunchArgument('enable_soft_filter', default_value='false'),
        DeclareLaunchArgument('soft_filter_max_diff', default_value='-1'),
        DeclareLaunchArgument('soft_filter_speckle_size', default_value='-1'),
        DeclareLaunchArgument('enable_decimation_filter', default_value='false'),
        DeclareLaunchArgument('enable_hdr_merge', default_value='false'),
        DeclareLaunchArgument('enable_sequence_id_filter', default_value='false'),
        DeclareLaunchArgument('enable_threshold_filter', default_value='false'),
        DeclareLaunchArgument('enable_noise_removal_filter', default_value='false'),
        DeclareLaunchArgument('enable_spatial_filter', default_value='false'),
        DeclareLaunchArgument('enable_temporal_filter', default_value='false'),
        DeclareLaunchArgument('enable_hole_filling_filter', default_value='false'),
        DeclareLaunchArgument('decimation_filter_scale_', default_value='-1'),
        DeclareLaunchArgument('sequence_id_filter_id', default_value='-1'),
        DeclareLaunchArgument('threshold_filter_max', default_value='-1'),
        DeclareLaunchArgument('threshold_filter_min', default_value='-1'),
        DeclareLaunchArgument('noise_removal_filter_min_diff', default_value='256'),
        DeclareLaunchArgument('noise_removal_filter_max_size', default_value='80'),
        DeclareLaunchArgument('spatial_filter_alpha', default_value='-1.0'),
        DeclareLaunchArgument('spatial_filter_diff_threshold', default_value='-1'),
        DeclareLaunchArgument('spatial_filter_magnitude', default_value='-1'),
        DeclareLaunchArgument('spatial_filter_radius', default_value='-1'),
        DeclareLaunchArgument('temporal_filter_diff_threshold', default_value='-1.0'),
        DeclareLaunchArgument('temporal_filter_weight', default_value='-1.0'),
        DeclareLaunchArgument('hole_filling_filter_mode', default_value=''),
        DeclareLaunchArgument('hdr_merge_exposure_1', default_value='-1'),
        DeclareLaunchArgument('hdr_merge_gain_1', default_value='-1'),
        DeclareLaunchArgument('hdr_merge_exposure_2', default_value='-1'),
        DeclareLaunchArgument('hdr_merge_gain_2', default_value='-1'),

        # ---- 其他 ----
        DeclareLaunchArgument('align_mode', default_value='SW'),
        DeclareLaunchArgument('diagnostic_period', default_value='1.0'),
        DeclareLaunchArgument('retry_on_usb3_detection_failure', default_value='false'),
        DeclareLaunchArgument('log_level', default_value='none'),
        DeclareLaunchArgument('enable_publish_extrinsic', default_value='false'),
        DeclareLaunchArgument('enable_d2c_viewer', default_value='false'),
        DeclareLaunchArgument('ir_info_url', default_value=''),
        DeclareLaunchArgument('color_info_url', default_value=''),
    ]

    all_args = fps_args + common_args

    # 组装参数列表
    parameters = [{arg.name: LaunchConfiguration(arg.name)} for arg in all_args]

    # ============================================================
    # ComposableNode — 与原厂相同，但容器用多线程版
    # ============================================================
    compose_node = ComposableNode(
        package='orbbec_camera',
        plugin='orbbec_camera::OBCameraNodeDriver',
        name=LaunchConfiguration('camera_name'),
        namespace='',
        parameters=parameters,
    )

    # ★ 关键优化：component_container_mt (多线程) 代替 component_container (单线程)
    # 单线程容器容易因驱动内部阻塞导致整个 container 卡死
    container = ComposableNodeContainer(
        name='camera_container',
        namespace='',
        package='rclcpp_components',
        executable='component_container_mt',
        composable_node_descriptions=[compose_node],
        output='screen',
    )

    return LaunchDescription(
        all_args + [
            GroupAction([
                PushRosNamespace(LaunchConfiguration('camera_name')),
                container,
            ]),
        ]
    )
