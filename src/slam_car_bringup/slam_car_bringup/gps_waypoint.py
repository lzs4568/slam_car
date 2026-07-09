#!/usr/bin/env python3
"""
GPS 航点接收节点: 订阅 /gps_waypoint (NavSatFix), 转为 ENU 坐标发布 /goal_pose
参考原点: 自动从 /gps/fix 获取第一个定位, 或通过参数硬编码 datum_lat/datum_lon
依赖: pip install pymap3d
"""
import math
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import NavSatFix
from geometry_msgs.msg import PoseStamped


class GpsWaypoint(Node):
    def __init__(self):
        super().__init__('gps_waypoint')

        self.declare_parameter('datum_lat', 0.0)
        self.declare_parameter('datum_lon', 0.0)
        self.declare_parameter('datum_alt', 0.0)

        self.datum_lat = self.get_parameter('datum_lat').value
        self.datum_lon = self.get_parameter('datum_lon').value
        self.datum_alt = self.get_parameter('datum_alt').value
        self.datum_set = self.datum_lat != 0.0 and self.datum_lon != 0.0

        # 订阅 GPS 定位（自动标定参考原点）
        self.gps_sub = self.create_subscription(
            NavSatFix, '/gps/fix', self.gps_fix_cb, 10)

        # 订阅航点（远程设备发布）
        self.waypoint_sub = self.create_subscription(
            NavSatFix, '/gps_waypoint', self.waypoint_cb, 10)

        # 发布导航目标
        self.goal_pub = self.create_publisher(PoseStamped, '/goal_pose', 10)

        self.get_logger().info(
            'GPS Waypoint node ready. Reference: %s',
            'MANUAL' if self.datum_set else 'AUTO (waiting for first /gps/fix)')

    def gps_fix_cb(self, msg: NavSatFix):
        if self.datum_set:
            return
        if not (math.isfinite(msg.latitude) and math.isfinite(msg.longitude)):
            return
        self.datum_lat = msg.latitude
        self.datum_lon = msg.longitude
        self.datum_alt = msg.altitude if math.isfinite(msg.altitude) else 0.0
        self.datum_set = True
        self.get_logger().info(
            'Auto datum set: lat=%.8f lon=%.8f alt=%.2f',
            self.datum_lat, self.datum_lon, self.datum_alt)

    def waypoint_cb(self, msg: NavSatFix):
        if not self.datum_set:
            self.get_logger().error(
                'No reference datum! Wait for /gps/fix or set datum_lat/datum_lon params.')
            return
        if not (math.isfinite(msg.latitude) and math.isfinite(msg.longitude)):
            self.get_logger().error('Invalid waypoint lat/lon.')
            return

        # ENU 转换 (pymap3d)
        try:
            from pymap3d import geodetic2enu
            e, n, u = geodetic2enu(
                msg.latitude, msg.longitude, msg.altitude,
                self.datum_lat, self.datum_lon, self.datum_alt)
        except ImportError:
            self.get_logger().error('pymap3d not installed. Run: pip install pymap3d')
            return

        goal = PoseStamped()
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.header.frame_id = 'map'
        goal.pose.position.x = e
        goal.pose.position.y = n
        goal.pose.position.z = u
        goal.pose.orientation.w = 1.0

        self.goal_pub.publish(goal)
        self.get_logger().info(
            'Waypoint: lat=%.7f lon=%.7f → ENU e=%.3f n=%.3f → /goal_pose',
            msg.latitude, msg.longitude, e, n)


def main(args=None):
    rclpy.init(args=args)
    node = GpsWaypoint()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
