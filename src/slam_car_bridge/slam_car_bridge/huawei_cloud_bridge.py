#!/usr/bin/env python3
"""
ESP32 传感器 → 华为云 IoT 桥接节点 (运行在 ELF2 上)

数据流: ESP32 UART0 → sensor_bridge_node → /sensors/status → 本节点 → MQTTS → 华为云

也支持直连串口模式 (ESP32 直接插 ELF2 USB):
  ros2 run slam_car_bridge huawei_cloud_bridge --ros-args -p serial_port:=/dev/ttyUSB0
"""
import json
import os
import re
import ssl
import time
import logging
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:
    import serial
except ImportError:
    serial = None

try:
    import paho.mqtt.client as mqtt
    from paho.mqtt.enums import CallbackAPIVersion
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False

# ═══════════════════════════════════════════
# 华为云 IoT 配置
# ═══════════════════════════════════════════
MQTT_HOST = os.getenv("HUAWEI_MQTT_HOST", "")
MQTT_PORT = int(os.getenv("HUAWEI_MQTT_PORT", "8883"))
DEVICE_ID = os.getenv("HUAWEI_DEVICE_ID", "")
USERNAME = os.getenv("HUAWEI_MQTT_USERNAME", DEVICE_ID)
PASSWORD = os.getenv("HUAWEI_MQTT_PASSWORD", "")
CLIENT_ID = os.getenv("HUAWEI_MQTT_CLIENT_ID", DEVICE_ID)
REPORT_TOPIC = f"$oc/devices/{DEVICE_ID}/sys/properties/report"
SERVICE_ID = "car_sensor"

logger = logging.getLogger('huawei_cloud')
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())


# ═══════════════════════════════════════════
# 数据映射
# ═══════════════════════════════════════════
def map_to_huawei(data: dict) -> dict:
    def _f(k, d=0.0):
        try: return float(data[k])
        except: return d
    def _i(k, d=0):
        try: return int(data[k])
        except: return d

    return {
        "temp":           _f("temp"),
        "hum":            _f("humi"),
        "mq2_gas_value":  _i("mq2"),
        "mq135_gas_value": _i("mq135"),
        "pm2_5":          _f("pm25"),
        "eco2":           _i("eco2"),
        "tvoc":           _i("tvoc"),
        "volt":           _f("volt"),
    }


def build_payload(properties: dict) -> str:
    return json.dumps({
        "services": [{"service_id": SERVICE_ID, "properties": properties}]
    }, ensure_ascii=False)


# ═══════════════════════════════════════════
# ROS2 节点
# ═══════════════════════════════════════════
class HuaweiCloudBridge(Node):
    def __init__(self):
        super().__init__('huawei_cloud_bridge')

        if not HAS_MQTT:
            self.get_logger().fatal("paho-mqtt 未安装! sudo pip3 install paho-mqtt")
            return

        # ── 参数: 串口路径 (空=用ROS2话题模式) ──
        self.declare_parameter('serial_port', '')
        self.declare_parameter('report_interval', 1.0)
        serial_port = self.get_parameter('serial_port').value
        self._report_interval = self.get_parameter('report_interval').value

        self._mqtt = None
        self._last_report = 0.0
        self._ser = None

        if serial_port:
            # 模式 A: 直连串口 (ESP32 插在 ELF2 上)
            self._init_serial(serial_port)
        else:
            # 模式 B: 订阅 ROS2 话题 (sensor_bridge_node 已读串口)
            self._sub = self.create_subscription(
                String, '/sensors/status', self._on_sensor_status, 10)
            self.get_logger().info("模式: 订阅 /sensors/status → 华为云")

        # MQTT 连接
        self._connect_mqtt()
        self.get_logger().info("华为云 IoT 桥接就绪")

    # ── 串口模式 ──
    def _init_serial(self, port: str):
        if serial is None:
            self.get_logger().fatal("pyserial 未安装!")
            return
        self._ser = serial.Serial(port, baudrate=115200, timeout=1.0)
        self._read_thread = threading.Thread(target=self._serial_loop, daemon=True)
        self._read_thread.start()
        self.get_logger().info(f"模式: 串口 {port} → 华为云")

    def _serial_loop(self):
        buf = ""
        while rclpy.ok():
            try:
                raw = self._ser.read(256)
                if raw:
                    buf += raw.decode('utf-8', errors='ignore')
                    while '\n' in buf:
                        line, buf = buf.split('\n', 1)
                        self._process_json(line.strip())
                else:
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"串口错误: {e}")
                time.sleep(1)

    # ── ROS2 话题模式 ──
    def _on_sensor_status(self, msg: String):
        self._process_json(msg.data)

    # ── 共用处理 ──
    def _process_json(self, line: str):
        if not line:
            return
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return

        # 节流上报
        now = time.monotonic()
        if now - self._last_report < self._report_interval:
            return
        self._last_report = now

        props = map_to_huawei(data)
        payload = build_payload(props)
        try:
            self._mqtt.publish(REPORT_TOPIC, payload, qos=1)
            logger.info(f"上报: {json.dumps(props, ensure_ascii=False)}")
        except Exception as e:
            logger.error(f"MQTT publish 失败: {e}")

    # ── MQTT ──
    def _connect_mqtt(self):
        self._mqtt = mqtt.Client(
            client_id=CLIENT_ID,
            protocol=mqtt.MQTTv311,
            callback_api_version=CallbackAPIVersion.VERSION2,
        )
        self._mqtt.username_pw_set(USERNAME, PASSWORD)
        self._mqtt.tls_set()
        self._mqtt.on_connect = lambda c, u, f, rc, p: logger.info(
            "MQTT 已连接" if rc == 0 else f"MQTT 连接失败: {rc}")
        self._mqtt.reconnect_delay_set(min_delay=5, max_delay=30)
        self._mqtt.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        self._mqtt.loop_start()

    def destroy_node(self):
        if self._mqtt:
            self._mqtt.loop_stop()
            self._mqtt.disconnect()
        if self._ser and self._ser.is_open:
            self._ser.close()
        super().destroy_node()


def main():
    rclpy.init()
    node = HuaweiCloudBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()
