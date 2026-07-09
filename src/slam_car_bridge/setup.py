from setuptools import setup

package_name = 'slam_car_bridge'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/voice_bridge.launch.py']),
        ('share/' + package_name + '/config', ['config/places.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='lzs4568',
    maintainer_email='lzs4568@github.com',
    description='ROS2 语音桥接 + 语义标注节点',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'annotation_node = slam_car_bridge.annotation_node:main',
            'ros2_voice_bridge = slam_car_bridge.ros2_voice_bridge:main',
            'sensor_bridge = slam_car_bridge.sensor_bridge_node:main',
            'rtsp_bridge = slam_car_bridge.rtsp_bridge:main',
            'yolo_mjpeg = slam_car_bridge.yolo_mjpeg:main',
            'gst_rtsp = slam_car_bridge.gst_rtsp:main',
            'hw_jpeg_bridge = slam_car_bridge.hw_jpeg_bridge:main',
            'mpp_jpeg_bridge = slam_car_bridge.mpp_jpeg_bridge:main',
            'huawei_cloud_bridge = slam_car_bridge.huawei_cloud_bridge:main',
            'places_bridge = slam_car_bridge.places_bridge:main',
            'voice_chat_bridge = slam_car_bridge.voice_chat_bridge:main',
        ],
    },
)
