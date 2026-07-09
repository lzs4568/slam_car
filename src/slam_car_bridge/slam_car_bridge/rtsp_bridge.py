#!/usr/bin/env python3
"""
YOLO → FFmpeg h264_rkmpp → RTSP

YOLO ~83fps, ffmpeg expects 15fps → 回调中限流, 只发每第N帧
"""
import time
import subprocess
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


class RtspBridge(Node):
    def __init__(self):
        super().__init__('rtsp_bridge')
        self._ffmpeg = None
        self._started = False
        self._last_send = 0.0
        self._interval = 1.0 / 15  # 15 fps
        self._sub = self.create_subscription(Image, '/yolo/annotated', self._cb, 10)
        self.get_logger().info('RTSP 桥接就绪 (15fps 限流)')

    def _start(self, w: int, h: int):
        cmd = [
            'ffmpeg', '-y',
            '-f', 'rawvideo', '-pix_fmt', 'bgr24',
            '-video_size', f'{w}x{h}',
            '-framerate', '15',
            '-i', 'pipe:0',
            '-vcodec', 'h264_rkmpp', '-b:v', '3M',
            '-preset', 'll', '-tune', 'zerolatency',
            '-g', '15',
            '-f', 'rtsp', '-rtsp_transport', 'tcp',
            'rtsp://127.0.0.1:8554/yolo'
        ]
        self._ffmpeg = subprocess.Popen(
            cmd, stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        self._started = True
        self.get_logger().info(f'FFmpeg h264_rkmpp 已启动 ({w}x{h})')

    def _cb(self, msg: Image):
        now = time.time()
        if now - self._last_send < self._interval:
            return  # 跳过此帧
        self._last_send = now

        try:
            if not self._started:
                self._start(msg.width, msg.height)

            # 直接取原始字节写入, 无需 reshape (bgr8 = continuous UINT8)
            raw = np.frombuffer(msg.data, dtype=np.uint8).tobytes()
            self._ffmpeg.stdin.write(raw)
            self._ffmpeg.stdin.flush()

        except BrokenPipeError:
            self.get_logger().error('管道断开, 重启FFmpeg', throttle_duration_sec=3)
            self._started = False
        except Exception as e:
            self.get_logger().error(str(e), throttle_duration_sec=5)

    def destroy_node(self):
        if self._ffmpeg and self._ffmpeg.poll() is None:
            self._ffmpeg.stdin.close()
            try:
                self._ffmpeg.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._ffmpeg.kill()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = RtspBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
