#!/usr/bin/env python3
"""
slip_detector — 轮子打滑检测节点
对比 IMU 陀螺仪角速度与轮式里程计 vyaw，差距过大时膨胀协方差，
EKF 自动降低 odom 权重，靠向 IMU。
"""
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu


class SlipDetector(Node):
    def __init__(self):
        super().__init__('slip_detector')

        self.declare_parameter('slip_threshold', 0.3)   # rad/s, |gyro - wheel_vyaw| > this → slip
        self.declare_parameter('cov_scale_max', 1000.0)  # max covariance multiplier

        self.slip_threshold = self.get_parameter('slip_threshold').value
        self.cov_scale_max = self.get_parameter('cov_scale_max').value

        self.gyro_z = 0.0
        self.latest_odom = None

        self.sub_odom = self.create_subscription(
            Odometry, '/odom_raw', self.odom_cb, 10)
        self.sub_imu = self.create_subscription(
            Imu, '/imu/data', self.imu_cb, 10)
        self.pub = self.create_publisher(Odometry, '/odom_corrected', 10)

        self.timer = self.create_timer(0.05, self.publish)

        self.get_logger().info(
            f'slip_detector started: slip_threshold={self.slip_threshold}, '
            f'cov_scale_max={self.cov_scale_max}'
        )

    def odom_cb(self, msg: Odometry):
        self.latest_odom = msg

    def imu_cb(self, msg: Imu):
        self.gyro_z = msg.angular_velocity.z

    def publish(self):
        if self.latest_odom is None:
            return

        # 重新读取参数，支持在线调参
        self.slip_threshold = self.get_parameter('slip_threshold').value
        self.cov_scale_max = self.get_parameter('cov_scale_max').value

        odom = self.latest_odom
        odom_vyaw = abs(odom.twist.twist.angular.z)
        gyro_z = abs(self.gyro_z)
        error = abs(gyro_z - odom_vyaw)

        # 软过渡: 0 ~ 1
        ratio = min(error / max(self.slip_threshold, 0.01), 1.0)
        scale = 1.0 + ratio * (self.cov_scale_max - 1.0)

        out = Odometry()
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = odom.header.frame_id
        out.child_frame_id = odom.child_frame_id
        out.pose = odom.pose
        out.twist = odom.twist

        # Inflate covariance on slip
        out.twist.covariance[0] = odom.twist.covariance[0] * scale    # vx
        out.twist.covariance[35] = odom.twist.covariance[35] * scale   # vyaw

        self.pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = SlipDetector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
