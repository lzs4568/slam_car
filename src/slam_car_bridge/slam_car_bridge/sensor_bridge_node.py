#!/usr/bin/env python3
"""
ESP32 传感器桥接节点
===================
读 ESP32 UART0 (CP2102) JSON 数据 → 发布 ROS2 topics

ESP32 输出格式 (500ms 间隔):
  {"temp":25.30,"humi":62.50,"mq2":128,"volt":12.53,"stream":false}

发布话题:
  /sensors/temperature   Float32  温度 (°C)
  /sensors/humidity      Float32  湿度 (%)
  /sensors/mq2           Int32    烟雾 ADC (0-4095)
  /sensors/mq135         Int32    空气质量 ADC
  /sensors/pm25          Float32  PM2.5 浓度 (mg/m³)
  /sensors/eco2          Int32    CO₂ (ppm)
  /sensors/tvoc          Int32    总挥发性有机物 (ppb)
  /sensors/battery       Float32  电池电压 (V)
  /sensors/status        String   完整 JSON (供华为云桥接)
"""

import json
import os
import sys
import time
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, Int32, String

try:
    import serial
except ImportError:
    serial = None


def find_sensor_port() -> str:
    """自动查找 ESP32 CP2102 传感器端口"""
    # 优先使用 udev 符号链接 (99-robot-usb.rules)
    import os as _os
    _symlink = "/dev/esp32_sensor"
    if _os.path.exists(_symlink):
        return _symlink
    # 回退: 自动扫描
    import glob
    for pat in ["/dev/ttyUSB*", "/dev/ttyACM*"]:
        ports = sorted(glob.glob(pat))
        if ports:
            return ports[0]
    raise FileNotFoundError("未找到传感器串口 (udev: /dev/esp32_sensor, 或 /dev/ttyUSB*, /dev/ttyACM*)")


class SensorBridgeNode(Node):
    def __init__(self, port: str = None):
        super().__init__('sensor_bridge')

        self._ser = None

        if serial is None:
            self.get_logger().fatal("pyserial 未安装!")
            return

        # ---- 串口 ----
        try:
            self._port = port or find_sensor_port()
        except FileNotFoundError as e:
            self.get_logger().fatal(str(e))
            return

        self._ser = serial.Serial(
            self._port, baudrate=115200, timeout=1.0,
            bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE)

        # ---- 发布者 ----
        self._pub_temp    = self.create_publisher(Float32, '/sensors/temperature', 10)
        self._pub_humi    = self.create_publisher(Float32, '/sensors/humidity', 10)
        self._pub_mq2     = self.create_publisher(Int32, '/sensors/mq2', 10)
        self._pub_mq135   = self.create_publisher(Int32, '/sensors/mq135', 10)
        self._pub_pm25    = self.create_publisher(Float32, '/sensors/pm25', 10)
        self._pub_eco2    = self.create_publisher(Int32, '/sensors/eco2', 10)
        self._pub_tvoc    = self.create_publisher(Int32, '/sensors/tvoc', 10)
        self._pub_battery = self.create_publisher(Float32, '/sensors/battery', 10)
        self._pub_status  = self.create_publisher(String, '/sensors/status', 10)

        # ---- 读取线程 ----
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

        self.get_logger().info(f"传感器桥接就绪: {self._port}")

    def _read_loop(self):
        buf = ""
        while self._running and rclpy.ok():
            try:
                raw = self._ser.read(256)
                if raw:
                    buf += raw.decode('utf-8', errors='ignore')
                    while '\n' in buf:
                        line, buf = buf.split('\n', 1)
                        self._parse_line(line.strip())
                else:
                    time.sleep(0.1)
            except serial.SerialException as e:
                self.get_logger().error(f"串口错误: {e}")
                time.sleep(1)
            except Exception as e:
                self.get_logger().error(f"读取异常: {e}")
                time.sleep(0.5)

    def _parse_line(self, line: str):
        if not line:
            return
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            self.get_logger().debug(f"非JSON: {line[:80]}")
            return

        # 温度
        if 'temp' in data:
            self._pub_temp.publish(Float32(data=data['temp']))

        # 湿度
        if 'humi' in data:
            self._pub_humi.publish(Float32(data=data['humi']))

        # 烟雾 MQ2
        if 'mq2' in data:
            self._pub_mq2.publish(Int32(data=data['mq2']))

        # 空气质量 MQ135
        if 'mq135' in data:
            self._pub_mq135.publish(Int32(data=data['mq135']))

        # PM2.5
        if 'pm25' in data:
            self._pub_pm25.publish(Float32(data=float(data['pm25'])))

        # SGP30: CO₂ + TVOC
        if 'eco2' in data:
            self._pub_eco2.publish(Int32(data=data['eco2']))
        if 'tvoc' in data:
            self._pub_tvoc.publish(Int32(data=data['tvoc']))

        # 电池
        if 'volt' in data:
            self._pub_battery.publish(Float32(data=data['volt']))

        # 完整状态
        if 'stream' in data or 'temp' in data:
            status = String(data=json.dumps(data, ensure_ascii=False))
            self._pub_status.publish(status)

    def destroy_node(self):
        self._running = False
        if self._ser and self._ser.is_open:
            self._ser.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    port = None
    try:
        port = find_sensor_port()
    except FileNotFoundError:
        pass

    node = SensorBridgeNode(port)
    if getattr(node, '_ser', None) is None and getattr(node, '_port', None) is None:
        node.get_logger().error("无串口可用，节点退出")
        rclpy.shutdown()
        return

    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
