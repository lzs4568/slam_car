#!/usr/bin/env python3
"""YOLO bgr8 → JPEG 转发 → web_video_server MJPEG 原生流"""
import sys, os, numpy as np
sys.path.insert(0, os.path.expanduser("~/.local/lib/python3.10/site-packages"))
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

class JpegRepub(Node):
    def __init__(self):
        super().__init__('jpeg_repub')
        self._pub = self.create_publisher(Image, '/yolo/jpeg', 10)
        self._sub = self.create_subscription(Image, '/yolo/annotated', self._cb, 10)
        self._seq = 0
        self._last_ts = 0.0
        self.get_logger().info('bgr8→JPEG 转发就绪')

    def _cb(self, msg):
        import time
        now = time.time()
        if now - self._last_ts < 0.066:  # ~15 FPS
            return
        self._last_ts = now
        try:
            raw = np.frombuffer(msg.data, dtype=np.uint8)
            raw = raw.reshape(msg.height, msg.width, 3)
            import cv2
            ok, jpg = cv2.imencode('.jpg', raw, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if not ok: return
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
    rclpy.init()
    node = JpegRepub()
    try: rclpy.spin(node)
    except: pass
    node.destroy_node(); rclpy.shutdown()

if __name__ == '__main__': main()
