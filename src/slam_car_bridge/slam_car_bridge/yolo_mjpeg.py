#!/usr/bin/env python3
"""YOLO bgr8 → JPEG → MJPEG HTTP (单文件, 零依赖中间件)

Qt 前端: http://192.168.5.10:8082/

curl 验证: curl http://192.168.5.10:8082/stream
"""
import sys, os, time, threading, numpy as np
sys.path.insert(0, os.path.expanduser("~/.local/lib/python3.10/site-packages"))
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import cv2

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

class YoloRelay(Node):
    def __init__(self):
        super().__init__('yolo_mjpeg')
        self.lock = threading.Lock()
        self.frame = None   # JPEG bytes
        self.count = 0
        self.sub = self.create_subscription(Image, '/yolo/annotated', self.cb, 10)
        self.get_logger().info('等待 /yolo/annotated...')

    def cb(self, msg):
        self.count += 1
        if self.count % 2 != 0:
            return
        try:
            raw = np.frombuffer(msg.data, dtype=np.uint8)
            raw = raw.reshape(msg.height, msg.width, 3)
            ok, jpg = cv2.imencode('.jpg', raw, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ok:
                with self.lock:
                    self.frame = jpg.tobytes()
        except Exception as e:
            self.get_logger().error(str(e), throttle_duration_sec=5)

    def get(self):
        with self.lock:
            return self.frame

class Handler(BaseHTTPRequestHandler):
    relay = None

    def do_GET(self):
        path = self.path.split('?')[0]  # 去掉 query string
        if path in ('/', '/index.html'):
            html = '<html><head><title>YOLO</title></head><body style="margin:0;background:#000"><img src="/stream" style="width:100vw"></body></html>'
            self._ok('text/html', html.encode())
        elif path == '/stream':
            self._stream()
        elif path == '/frame.jpg':
            frame = Handler.relay.get()
            if frame:
                self._ok('image/jpeg', frame)
            else:
                self.send_response(503); self.end_headers()
        else:
            self.send_response(404); self.end_headers()

    def _ok(self, ct, data):
        self.send_response(200)
        self.send_header('Content-type', ct)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(data)

    def _stream(self):
        self.send_response(200)
        self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        self.end_headers()
        last = None
        while True:
            try:
                frame = Handler.relay.get()
                if frame and frame != last:
                    last = frame
                    self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n' % len(frame))
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
                    self.wfile.flush()
                time.sleep(0.1)
            except (BrokenPipeError, ConnectionResetError):
                break
            except Exception:
                break

    def log_message(self, *a): pass

def main():
    rclpy.init()
    relay = YoloRelay()
    Handler.relay = relay
    t = threading.Thread(target=rclpy.spin, args=(relay,), daemon=True)
    t.start()
    # 等待第一帧
    for _ in range(50):
        if relay.get(): break
        time.sleep(0.1)
    print(f'http://192.168.5.10:8082/  frames_rcvd={relay.count}', flush=True)
    ThreadingHTTPServer(('0.0.0.0', 8082), Handler).serve_forever()
    relay.destroy_node(); rclpy.shutdown()

if __name__ == '__main__': main()
