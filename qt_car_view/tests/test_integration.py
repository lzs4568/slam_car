"""tests/test_integration.py — 信号链路集成测试"""
import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import QCoreApplication

# 确保 QApplication 存在（pytest-qt 提供或手动创建）
from PyQt6.QtWidgets import QApplication

_app = QApplication.instance()
if _app is None:
    _app = QApplication(sys.argv)


from data_manager import DataManager, TrajectoryCache, check_thresholds
from mqtt_client import parse_sensor_message


class TestSignalChainMqttToDataManager:
    """验证 MQTT 消息解析 → DataManager 的完整链路。"""

    def test_full_pipeline_sensor_data(self, qtbot):
        """模拟 MQTT 消息到达到传感器显示的信号链路"""
        dm = DataManager()

        # 收集信号
        received_display = []
        dm.sensor_display.connect(lambda d: received_display.append(d))

        # 模拟 MQTT 消息
        payload = json.dumps({
            "services": [{
                "service_id": "car_sensor",
                "properties": {
                    "temp": 26.5,
                    "hum": 58.2,
                    "mq2_gas_value": 320,
                    "mq135_gas_value": 185,
                    "pm2_5": 15,
                    "battery": 12.4,
                }
            }]
        })

        # 解析
        data = parse_sensor_message(payload)
        assert data is not None

        # 送入 DataManager
        dm.on_sensor_data(data)

        assert len(received_display) == 1
        assert received_display[0]["temp"] == 26.5
        assert received_display[0]["battery"] == 12.4

    def test_threshold_alarm_in_chain(self, qtbot):
        """阈值超限触发 alarm 信号"""
        dm = DataManager()

        alarms = []
        dm.alarm_triggered.connect(lambda s, d: alarms.append((s, d)))

        payload = json.dumps({
            "services": [{
                "service_id": "car_sensor",
                "properties": {
                    "temp": 99.0,
                    "mq2_gas_value": 999,
                    "battery": 8.0,
                }
            }]
        })

        data = parse_sensor_message(payload)
        dm.on_sensor_data(data)

        assert len(alarms) == 3
        alarm_keys = {a[0] for a in alarms}
        assert "temp" in alarm_keys
        assert "mq2_gas_value" in alarm_keys
        assert "battery" in alarm_keys


class TestTrajectoryFlow:
    """轨迹数据流测试。"""

    def test_gps_to_trajectory(self, qtbot):
        dm = DataManager()

        gps_positions = []
        dm.gps_display.connect(lambda lat, lng: gps_positions.append((lat, lng)))

        dm.on_gps_position(31.2, 121.4, 10.0)
        dm.on_gps_position(31.3, 121.5, 10.0)

        assert len(gps_positions) == 2
        assert gps_positions[-1] == (31.3, 121.5)

        traj = dm.get_trajectory()
        assert len(traj) == 2
        assert traj[-1] == {"lat": 31.3, "lng": 121.5}

    def test_clear_trajectory_signal(self, qtbot):
        dm = DataManager()
        cleared = []
        dm.trajectory_clear.connect(lambda: cleared.append(True))

        dm.on_gps_position(31.2, 121.4, 10.0)
        dm.clear_trajectory()

        assert len(cleared) == 1
        assert len(dm.get_trajectory()) == 0
