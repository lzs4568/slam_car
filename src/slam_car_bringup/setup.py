from setuptools import setup
import os
from glob import glob

package_name = 'slam_car_bringup'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob(os.path.join('launch', '*.launch.py'))),
        (os.path.join('share', package_name, 'urdf'),
            glob(os.path.join('urdf', '*.urdf'))),
        (os.path.join('share', package_name, 'meshes'),
            glob(os.path.join('meshes', '*.STL'))),
        (os.path.join('share', package_name, 'rviz'),
            glob(os.path.join('rviz', '*.rviz'))),
        (os.path.join('share', package_name, 'config'),
            glob(os.path.join('config', '*.yaml'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='lzs4568',
    maintainer_email='lzs4568@gmail.com',
    description='SLAM小车启动配置',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'gps_waypoint = slam_car_bringup.gps_waypoint:main',
            'vel_scaler_node = slam_car_bringup.vel_scaler_node:main',
            'slip_detector = slam_car_bringup.slip_detector:main',
        ],
    },
)
