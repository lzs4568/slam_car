from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


# RTAB-Map 启动说明：
# 1) 重建地图: delete_db_on_start=true, localization=false
# 2) 增量建图: delete_db_on_start=false, localization=false
# 3) 仅定位:   delete_db_on_start=false, localization=true
# 4) GPS约束:  use_gps=true (需先连接UM960)
def generate_launch_description():
    # 数据库存放路径，默认保存在 ~/data/map/rtabmap.db
    database_path = ParameterValue(LaunchConfiguration('database_path'), value_type=str)
    # 启动时是否删除旧数据库
    delete_db_on_start = ParameterValue(LaunchConfiguration('delete_db_on_start'), value_type=bool)
    # 是否进入仅定位模式
    localization = LaunchConfiguration('localization')
    # 是否启用 GPS 约束
    use_gps = LaunchConfiguration('use_gps')
    gps_topic = LaunchConfiguration('gps_topic')

    # localization=true: 只定位不扩图；false: 正常增量建图
    incremental_memory = ParameterValue(PythonExpression([
        "'false' if '", localization, "' == 'true' else 'true'"
    ]), value_type=str)
    # 仅定位时把数据库中的节点全部加载进工作内存
    init_wm_with_all_nodes = ParameterValue(localization, value_type=str)

    rtabmap_slam = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        output='screen',
        parameters=[{
            'frame_id':                  'base_link',
            'odom_frame_id':             'odom',
            'map_frame_id':              'map',
            'publish_tf':                True,
            'tf_publish_rate':           10.0,
            'use_sim_time':              False,
            'approx_sync':               True,
            'approx_sync_max_interval':  0.3,
            'queue_size':                5,
            'publish_null_when_lost':    False,
            'subscribe_scan':            True,
            'subscribe_rgb':             True,
            'subscribe_depth':           True,
            # # GPS 因子
            # 'subscribe_gps':             ParameterValue(PythonExpression([
            #     "True if '", use_gps, "' == 'true' else False"
            # ]), value_type=bool),
            'gps_topic':                 gps_topic,
            # 地图持久化
            'delete_db_on_start':        delete_db_on_start,
            'database_path':             database_path,
            'Mem/IncrementalMemory':     incremental_memory,
            'Mem/InitWMWithAllNodes':    init_wm_with_all_nodes,
            'wait_for_transform':        0.5,
            'rgbd_decimation':           4,
            'gen_scan':                  False,
            'Grid/FromDepth':           'false',
            'cloud_output_voxel_size':   0.05,
            'Reg/Strategy':              '1',
            'Reg/Force3DoF':            'false',
            'Icp/VoxelSize':     '0.08',
            'Icp/MaxCorrespondenceDistance': '0.3',
            'Icp/Iterations': '50',
            'Icp/PointToPlane':  'false',
            'Odom/Strategy':             '0',
        }],
        remappings=[
            ('rgb/image',        '/camera/color/image_raw'),
            ('rgb/camera_info',  '/camera/color/camera_info'),
            ('depth/image',      '/camera/depth/image_raw'),
            ('depth/camera_info','/camera/depth/camera_info'),
            ('odom',            '/odometry/filtered'),
            ("scan",            "/scan"),
            ('grid_map',        '/rtabmap/grid_map'),
            ('cloud_map',       '/rtabmap/cloud_map'),
        ],
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'database_path',
            default_value='~/data/map/rtabmap.db',
            description='RTAB-Map database file path.'
        ),
        DeclareLaunchArgument(
            'delete_db_on_start',
            default_value='false',
            description='Set true to rebuild map from scratch.'
        ),
        DeclareLaunchArgument(
            'localization',
            default_value='false',
            description='Set true to localize without adding new nodes.'
        ),
        DeclareLaunchArgument(
            'use_gps',
            default_value='false',
            description='Set true to enable GPS factor in RTAB-Map optimization.'
        ),
        DeclareLaunchArgument(
            'gps_topic',
            default_value='/gps/fix',
            description='GPS fix topic (sensor_msgs/NavSatFix).'
        ),
        rtabmap_slam,
    ])
