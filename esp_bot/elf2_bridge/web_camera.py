#!/usr/bin/env python3
"""
MJPEG 相机推流 HTTP 服务 (无 cv_bridge 依赖)
=============================================
直接从 ROS2 bgr8 → numpy → JPEG → MJPEG HTTP → 浏览器

浏览器打开:
  http://192.168.5.10:8081/
"""

import os
import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import numpy as np
import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


class CameraRelayNode(Node):
    def __init__(self):
        super().__init__('web_camera')
        self._lock = threading.Lock()
        self._raw_frame = None
        self._yolo_frame = None

        self._raw_sub = self.create_subscription(
            Image, '/camera/color/image_raw', self._raw_cb, 10)
        self._yolo_sub = self.create_subscription(
            Image, '/yolo/annotated', self._yolo_cb, 10)

        self.get_logger().info("MJPEG 推流就绪 — 等待图像...")

    def _imgmsg_to_jpeg(self, msg: Image, max_w: int = 640) -> bytes:
        """Image msg (bgr8) → JPEG bytes, no cv_bridge needed"""
        try:
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(
                msg.height, msg.width, 3)
            h, w = arr.shape[:2]
            if w > max_w:
                scale = max_w / w
                arr = cv2.resize(arr, (max_w, int(h * scale)))
            _, jpeg = cv2.imencode('.jpg', arr, [cv2.IMWRITE_JPEG_QUALITY, 45])
            return jpeg.tobytes()
        except Exception as e:
            self.get_logger().error(f"编码失败: {e}", throttle_duration_sec=5)
            return None

    def _raw_cb(self, msg: Image):
        jpeg = self._imgmsg_to_jpeg(msg)
        if jpeg:
            with self._lock:
                self._raw_frame = jpeg
            if self._raw_frame is None:  # 第一帧
                self.get_logger().info("相机图像已连接")

    def _yolo_cb(self, msg: Image):
        jpeg = self._imgmsg_to_jpeg(msg)
        if jpeg:
            with self._lock:
                self._yolo_frame = jpeg

    def get_frame(self, source: str):
        with self._lock:
            if source == 'camera':
                return self._raw_frame
            return self._yolo_frame


class MJPEGHandler(BaseHTTPRequestHandler):
    relay_node: CameraRelayNode = None

    def do_GET(self):
        if self.path == '/' or self.path.startswith('/index'):
            self._serve_index()
        elif self.path.startswith('/camera'):
            self._serve_stream('camera')
        elif self.path.startswith('/yolo'):
            self._serve_stream('yolo')
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_index(self):
        html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>SLAM 小车视觉</title>
<style>
body{font-family:sans-serif;background:#1a1a2e;color:#eee;margin:0;padding:20px}
h1{text-align:center;color:#e94560}
.grid{display:flex;flex-wrap:wrap;gap:20px;justify-content:center}
.panel{background:#16213e;border-radius:8px;padding:10px;max-width:660px}
.panel h2{margin:0 0 8px;font-size:14px;color:#fff}
img{width:100%;border-radius:4px}
</style></head><body>
<h1>SLAM 小车视觉</h1>
<div class="grid">
<div class="panel"><h2>原始相机</h2><img src="/camera"></div>
<div class="panel"><h2>YOLO 检测</h2><img src="/yolo"></div>
</div></body></html>"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())

    def _serve_stream(self, source: str):
        self.send_response(200)
        self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        no_img = 0
        while True:
            try:
                frame = MJPEGHandler.relay_node.get_frame(source)
                if frame:
                    no_img = 0
                    self.wfile.write(b'--frame\r\n')
                    self.wfile.write(b'Content-Type: image/jpeg\r\n')
                    self.wfile.write(f'Content-Length: {len(frame)}\r\n\r\n'.encode())
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
                    self.wfile.flush()
                    time.sleep(0.15)
                else:
                    no_img += 1
                    if no_img == 1:
                        blank = np.zeros((240, 424, 3), dtype=np.uint8)
                        cv2.putText(blank, 'Waiting...', (20, 120),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        _, jpeg = cv2.imencode('.jpg', blank,
                                               [cv2.IMWRITE_JPEG_QUALITY, 30])
                        self.wfile.write(b'--frame\r\n')
                        self.wfile.write(b'Content-Type: image/jpeg\r\n')
                        self.wfile.write(f'Content-Length: {len(jpeg)}\r\n\r\n'.encode())
                        self.wfile.write(jpeg.tobytes())
                        self.wfile.write(b'\r\n')
                        self.wfile.flush()
                    time.sleep(0.5)
            except (BrokenPipeError, ConnectionResetError):
                break
            except Exception:
                break

    def log_message(self, format, *args):
        pass


def main():
    rclpy.init(args=None)
    node = CameraRelayNode()
    MJPEGHandler.relay_node = node

    ros_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    ros_thread.start()

    server = HTTPServer(('0.0.0.0', 8081), MJPEGHandler)
    print(f"http://192.168.5.10:8081/")
    server.serve_forever()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
