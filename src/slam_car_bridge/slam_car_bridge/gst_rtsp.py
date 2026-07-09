#!/usr/bin/env python3
"""
YOLO bgr8 → GStreamer mpph264enc → RTSP (单进程硬编码)

管道: appsrc(BGR) → videoconvert → mpph264enc → h264parse → rtph264pay → RTSP
前端: rtsp://192.168.5.10:8554/yolo
"""
import sys, time, threading, logging
import numpy as np

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GLib

Gst.init(None)

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

log = logging.getLogger('gst_rtsp')
log.setLevel(logging.INFO)
log.addHandler(logging.StreamHandler(sys.stderr))


class YoloRtspNode(Node):
    def __init__(self):
        super().__init__('gst_rtsp')
        self._appsrc = None
        self._appsink_lock = threading.Lock()
        self._frame_count = 0
        self._last_time = 0.0
        self._w = self._h = 0
        self._caps_set = False
        self._pts = 0  # 递增 PTS

        self._setup_server()
        self._sub = self.create_subscription(Image, '/yolo/annotated', self._cb, 10)
        self.get_logger().info('RTSP 就绪 → rtsp://192.168.5.10:8554/yolo')

    def _setup_server(self):
        srv = GstRtspServer.RTSPServer()
        srv.set_service('8554')
        srv.set_address('0.0.0.0')

        fac = GstRtspServer.RTSPMediaFactory()
        # 424x240 BGR 是 YOLO 输出分辨率，硬编码避免动态 caps 协商失败
        fac.set_launch(
            '( appsrc name=src is-live=true block=true '
            '  format=GST_FORMAT_TIME max-bytes=2000000 '
            '  caps=video/x-raw,format=BGR,width=424,height=240,framerate=15/1 '
            '! videoconvert '
            '! video/x-raw,format=NV12 '
            '! mpph264enc '
            '! h264parse '
            '! rtph264pay name=pay0 config-interval=1 )'
        )
        fac.set_shared(True)
        fac.connect('media-configure', self._on_configure)

        srv.get_mount_points().add_factory('/yolo', fac)
        srv.attach(None)
        self.get_logger().info('RTSP server :8554 已启动')

    def _on_configure(self, fac, media):
        """客户端连入/重连 → 获取新的 appsrc"""
        el = media.get_element()
        if not el:
            return
        src = el.get_by_name('src')
        if not src:
            return

        with self._appsink_lock:
            self._appsrc = src
            self._caps_set = False
            self._pts = 0
        self.get_logger().info('客户端连入, appsrc 就绪')

    def _cb(self, msg):
        self._frame_count += 1
        if self._frame_count % 5 != 0:
            return
        now = time.time()
        if now - self._last_time < 0.066:
            return
        self._last_time = now

        # 线程安全读取 appsrc
        with self._appsink_lock:
            src = self._appsrc

        if not src:
            return

        try:
            self._pts += 1

            # 零拷贝 GstBuffer
            buf = Gst.Buffer.new_wrapped(
                np.frombuffer(msg.data, dtype=np.uint8).tobytes())
            buf.pts = self._pts * (Gst.SECOND // 15)
            buf.duration = Gst.SECOND // 15

            ret = src.emit('push-buffer', buf)
            if ret == Gst.FlowReturn.FLUSHING:
                # 管道关闭中 (客户端断开), 复位等待重连
                with self._appsink_lock:
                    self._appsrc = None
                    self._caps_set = False
                log.debug('管道关闭, 等待客户端重连...')
            elif ret != Gst.FlowReturn.OK:
                log.warning('push-buffer: %s', ret)

        except Exception as e:
            log.error(str(e))


def main():
    rclpy.init(args=sys.argv)
    node = YoloRtspNode()

    g_mainloop = GLib.MainLoop()
    t = threading.Thread(target=g_mainloop.run, daemon=True)
    t.start()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    g_mainloop.quit()
    node.destroy_node()
    rclpy.shutdown()
