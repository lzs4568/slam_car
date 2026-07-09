#!/usr/bin/env python3
"""MPP 硬件 JPEG 编码桥接: /yolo/annotated (bgr8) → mppjpegenc → /yolo/jpeg (HW)"""
import sys
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import numpy as np

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

Gst.init(None)

PIPE = (
    'appsrc name=src block=true format=GST_FORMAT_TIME caps=video/x-raw,format=BGR,width=424,height=240,framerate=30/1 '
    '! jpegenc quality=85 '
    '! appsink name=sink max-buffers=1 drop=true sync=false'
)


class MppJpegNode(Node):
    def __init__(self):
        super().__init__('mpp_jpeg_bridge')
        self._pub = self.create_publisher(Image, '/yolo/jpeg', 10)
        self._sub = self.create_subscription(Image, '/yolo/annotated', self._cb, 10)
        self._pipeline = Gst.parse_launch(PIPE)
        self._src = self._pipeline.get_by_name('src')
        self._sink = self._pipeline.get_by_name('sink')
        self._pipeline.set_state(Gst.State.PLAYING)
        self._count = 0
        self.get_logger().info('MPP HW JPEG bridge ready (GStreamer mppjpegenc)')

    def _cb(self, msg):
        self._count += 1
        if self._count % 2 != 0:   # YOLO ~80fps → 编码 ~40fps
            return
        try:
            raw = np.frombuffer(msg.data, dtype=np.uint8)
            h, w = msg.height, msg.width

            # 推 BGR 帧到 pipeline
            buf = Gst.Buffer.new_allocate(None, len(raw), None)
            buf.fill(0, raw.tobytes())
            buf.pts = buf.dts = Gst.CLOCK_TIME_NONE
            buf.duration = Gst.SECOND // 30

            # 更新 caps（分辨率可能变化）
            caps = Gst.Caps.from_string(
                f'video/x-raw,format=BGR,width={w},height={h},framerate=30/1')
            self._src.set_property('caps', caps)

            ret = self._src.emit('push-buffer', buf)
            if ret != Gst.FlowReturn.OK:
                self.get_logger().warn(f'push-buffer failed: {ret}', throttle_duration_sec=5)
                return

            # 取编码结果 (50ms 超时)
            sample = self._sink.emit('try-pull-sample', Gst.SECOND // 20)
            if not sample:
                return
            gst_buf = sample.get_buffer()
            ok, map_info = gst_buf.map(Gst.MapFlags.READ)
            if not ok:
                return

            out = Image()
            out.header.stamp = msg.header.stamp
            out.header.frame_id = msg.header.frame_id
            out.height = h
            out.width = w
            out.encoding = 'jpeg'
            out.step = map_info.size
            out.data = map_info.data[:]
            gst_buf.unmap(map_info)
            self._pub.publish(out)

        except Exception as e:
            self.get_logger().error(str(e), throttle_duration_sec=5)

    def destroy_node(self):
        self._pipeline.set_state(Gst.State.NULL)
        super().destroy_node()


def main():
    rclpy.init(args=sys.argv)
    node = MppJpegNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
