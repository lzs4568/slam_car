#!/usr/bin/env python3
"""
JPEG 压缩桥接: /yolo/annotated (bgr8 305KB) → cv2.imencode → /yolo/jpeg (~3KB)

压缩比 ~100:1, DDS 带宽 ~48Mbps → ~0.5Mbps
424x240 下 cv2.imencode <1ms, RK3588 8核完全不影响建图
"""
import sys, time
import numpy as np
import cv2

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


class HwJpegBridge(Node):
    def __init__(self):
        super().__init__('hw_jpeg_bridge')
        self._pub = self.create_publisher(Image, '/yolo/jpeg', 10)
        self._sub = self.create_subscription(Image, '/yolo/annotated', self._cb, 10)
        self._count = 0
        self._last_time = 0.0
        self.get_logger().info('JPEG 压缩桥接就绪 → /yolo/jpeg')

    def _cb(self, msg):
        self._count += 1
        if self._count % 4 != 0:
            return
        now = time.time()
        if now - self._last_time < 0.066:
            return
        self._last_time = now

        try:
            raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
            ok, jpg = cv2.imencode('.jpg', raw, [cv2.IMWRITE_JPEG_QUALITY, 30])
            if not ok:
                return

            out = Image()
            out.header.stamp = msg.header.stamp
            out.header.frame_id = msg.header.frame_id
            out.height = msg.height
            out.width = msg.width
            out.encoding = 'jpeg'
            out.step = len(jpg)
            out.data = jpg.tobytes()
            self._pub.publish(out)

        except Exception as e:
            self.get_logger().error(str(e), throttle_duration_sec=5)


def main():
    rclpy.init(args=sys.argv)
    node = HwJpegBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()
