"""Tests for mqtt_client.py — Huawei IoT MQTT client."""
import sys
import json
import hashlib
import hmac
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mqtt_client import (
    parse_sensor_message,
    huawei_device_password,
    huawei_app_username,
)


class TestMqttMessageParsing:
    def test_valid_huawei_services_message(self):
        """标准华为云属性上报 JSON 解析"""
        payload = json.dumps({
            "services": [{
                "service_id": "car_sensor",
                "properties": {
                    "temp": 26.5,
                    "hum": 58.2,
                    "mq2_gas_value": 320,
                    "mq135_gas_value": 185,
                    "pm2_5": 15,
                    "battery": 12.4
                }
            }]
        })
        result = parse_sensor_message(payload)
        assert result is not None
        assert result["temp"] == 26.5
        assert result["hum"] == 58.2
        assert result["mq2_gas_value"] == 320
        assert result["mq135_gas_value"] == 185
        assert result["pm2_5"] == 15
        assert result["battery"] == 12.4

    def test_wrong_service_id_ignored(self):
        """非 car_sensor 的 service 被忽略"""
        payload = json.dumps({
            "services": [{
                "service_id": "other_service",
                "properties": {"temp": 99.9}
            }]
        })
        result = parse_sensor_message(payload)
        assert result is None

    def test_no_services_field(self):
        """缺少 services 字段时返回 None"""
        payload = json.dumps({"other": "data"})
        result = parse_sensor_message(payload)
        assert result is None

    def test_invalid_json_returns_none(self):
        """非法 JSON 返回 None"""
        result = parse_sensor_message("not json{{{")
        assert result is None

    def test_empty_string_returns_none(self):
        result = parse_sensor_message("")
        assert result is None

    def test_partial_properties_ok(self):
        """只上报部分属性是合法的"""
        payload = json.dumps({
            "services": [{
                "service_id": "car_sensor",
                "properties": {
                    "temp": 30.0,
                    "battery": 11.5
                }
            }]
        })
        result = parse_sensor_message(payload)
        assert result is not None
        assert result["temp"] == 30.0
        assert result["battery"] == 11.5
        assert "hum" not in result


class TestHuaweiIotAuth:
    """华为云 IoT 认证工具测试"""

    def test_device_password_is_64_char_hex(self):
        pwd, ts = huawei_device_password("secret123")
        assert len(pwd) == 64
        assert all(c in "0123456789abcdef" for c in pwd)
        assert len(ts) == 10  # YYYYMMDDHH

    def test_device_password_uses_beijing_time(self):
        pwd, ts = huawei_device_password("secret")
        import datetime
        now = int(datetime.datetime.now().strftime("%H"))
        ts_hour = int(ts[-2:])
        # 北京时间 (UTC+8) 小时偏移合理
        diff = abs(ts_hour - now) % 24
        assert diff in (8, 16) or diff < 2  # UTC+8 时区

    def test_app_username_format(self):
        uname = huawei_app_username("key123", ts_ms=1700000000000)
        assert uname == "accessKey=key123|timestamp=1700000000000"

    def test_app_username_with_instance_id(self):
        uname = huawei_app_username("key123", "inst456", ts_ms=1700000000000)
        assert "accessKey=key123" in uname
        assert "instanceId=inst456" in uname
        assert "timestamp=1700000000000" in uname

    def test_app_username_auto_timestamp(self):
        uname = huawei_app_username("key123")
        assert "accessKey=key123" in uname
        assert "timestamp=" in uname
        ts_str = uname.split("timestamp=")[1].split("|")[0]
        assert len(ts_str) == 13  # 毫秒时间戳


class TestMqttClientConfig:
    """验证 MqttClient 构造参数传递正确"""

    def test_access_key_mode(self):
        from mqtt_client import MqttClient
        client = MqttClient(
            access_key="test_key",
            access_code="test_code",
            host="test.example.com",
        )
        username, password = client._build_auth()
        assert "accessKey=test_key" in username
        assert "timestamp=" in username
        assert password == "test_code"

    def test_device_secret_mode(self):
        from mqtt_client import MqttClient
        client = MqttClient(
            username="test_device",
            device_secret="test_secret_xyz",
            host="test.example.com",
        )
        username, password = client._build_auth()
        assert username == "test_device"
        assert len(password) == 64  # SHA256 hex

    def test_access_key_with_instance_id(self):
        from mqtt_client import MqttClient
        client = MqttClient(
            access_key="test_key",
            access_code="test_code",
            instance_id="inst123",
            host="test.example.com",
        )
        username, password = client._build_auth()
        assert "accessKey=test_key" in username
        assert "instanceId=inst123" in username
        assert password == "test_code"

    def test_static_password_fallback(self):
        from mqtt_client import MqttClient
        client = MqttClient(
            username="user",
            password="pass",
            host="test.example.com",
        )
        username, password = client._build_auth()
        assert username == "user"
        assert password == "pass"
