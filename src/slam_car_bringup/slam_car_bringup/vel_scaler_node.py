#!/usr/bin/env python3
"""
vel_scaler_node — cmd_vel 速度缩放节点
对 angular.z 乘以 angular_scale，解决转弯堵转问题。
可通过 ros2 param set 在线调参。
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class VelScaler(Node):
    def __init__(self):
        super().__init__('vel_scaler')

        self.declare_parameter('angular_scale', 2.0)
        self.declare_parameter('linear_scale', 1.0)

        self.angular_scale = self.get_parameter('angular_scale').value
        self.linear_scale = self.get_parameter('linear_scale').value

        self.get_logger().info(
            f'vel_scaler started: angular_scale={self.angular_scale}, '
            f'linear_scale={self.linear_scale}'
        )

        self.sub = self.create_subscription(
            Twist, '/cmd_vel_raw', self.callback, 10
        )
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)

    def callback(self, msg: Twist):
        # 每次回调重新读取参数，支持在线调参
        self.angular_scale = self.get_parameter('angular_scale').value
        self.linear_scale = self.get_parameter('linear_scale').value

        scaled = Twist()
        scaled.linear.x = msg.linear.x * self.linear_scale
        scaled.linear.y = msg.linear.y * self.linear_scale
        scaled.linear.z = msg.linear.z * self.linear_scale
        scaled.angular.x = msg.angular.x * self.angular_scale
        scaled.angular.y = msg.angular.y * self.angular_scale
        scaled.angular.z = msg.angular.z * self.angular_scale
        self.pub.publish(scaled)


def main(args=None):
    rclpy.init(args=args)
    node = VelScaler()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
