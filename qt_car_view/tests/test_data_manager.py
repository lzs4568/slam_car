"""Tests for data_manager.py — threshold checking and trajectory cache."""
import sys
import json
import tempfile
import os
import pytest
from pathlib import Path
from collections import deque

# data_manager 不依赖 PyQt 也能测试核心逻辑（用 QObject 需要 QApplication，
# 我们先测纯函数部分，避免 pytest-qt 依赖链）
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_manager import (
    DEFAULT_THRESHOLDS,
    check_thresholds,
    TrajectoryCache,
)


class TestThresholds:
    def test_default_thresholds_loaded(self):
        """默认阈值包含全部 9 个键 (6 传感器，其中 3 个有上下限)"""
        assert len(DEFAULT_THRESHOLDS) == 9
        assert DEFAULT_THRESHOLDS["temp_high"] == 60.0
        assert DEFAULT_THRESHOLDS["temp_low"] == 0.0
        assert DEFAULT_THRESHOLDS["hum_high"] == 95.0
        assert DEFAULT_THRESHOLDS["mq2_gas_value_high"] == 500
        assert DEFAULT_THRESHOLDS["battery_low"] == 10.5

    def test_temp_within_threshold_no_alarm(self):
        """温度在阈值范围内，不触发告警"""
        thresholds = DEFAULT_THRESHOLDS
        data = {"temp": 26.5}
        alarms = check_thresholds(data, thresholds)
        assert "temp" not in alarms

    def test_temp_high_alarm(self):
        """温度超过上限，触发告警"""
        thresholds = DEFAULT_THRESHOLDS
        data = {"temp": 75.0}
        alarms = check_thresholds(data, thresholds)
        assert "temp" in alarms
        assert alarms["temp"] == "high"

    def test_temp_low_alarm(self):
        """温度低于下限，触发告警"""
        thresholds = DEFAULT_THRESHOLDS
        data = {"temp": -5.0}
        alarms = check_thresholds(data, thresholds)
        assert "temp" in alarms
        assert alarms["temp"] == "low"

    def test_battery_normal(self):
        thresholds = DEFAULT_THRESHOLDS
        data = {"battery": 12.0}
        alarms = check_thresholds(data, thresholds)
        assert "battery" not in alarms

    def test_battery_low_alarm(self):
        thresholds = DEFAULT_THRESHOLDS
        data = {"battery": 9.5}
        alarms = check_thresholds(data, thresholds)
        assert "battery" in alarms
        assert alarms["battery"] == "low"

    def test_mq2_alarm(self):
        thresholds = DEFAULT_THRESHOLDS
        data = {"mq2_gas_value": 600}
        alarms = check_thresholds(data, thresholds)
        assert "mq2_gas_value" in alarms
        assert alarms["mq2_gas_value"] == "high"

    def test_partial_data_checks_only_present_sensors(self):
        """只传入部分传感器数据，仅检查传入的"""
        thresholds = DEFAULT_THRESHOLDS
        data = {"temp": 70.0}
        alarms = check_thresholds(data, thresholds)
        assert "temp" in alarms
        assert "hum" not in alarms

    def test_boundary_value_no_alarm(self):
        """边界值不触发告警"""
        thresholds = DEFAULT_THRESHOLDS
        data = {"temp": 60.0}  # 等于上限，不告警
        alarms = check_thresholds(data, thresholds)
        assert "temp" not in alarms


class TestTrajectoryCache:
    def test_new_cache_is_empty(self):
        cache = TrajectoryCache(maxlen=2000)
        assert len(cache.get_all()) == 0

    def test_add_point(self):
        cache = TrajectoryCache(maxlen=2000)
        cache.add(31.2, 121.4)
        assert len(cache.get_all()) == 1
        assert cache.get_all()[0] == {"lat": 31.2, "lng": 121.4}

    def test_add_multiple_points(self):
        cache = TrajectoryCache(maxlen=2000)
        cache.add(31.2, 121.4)
        cache.add(31.3, 121.5)
        cache.add(31.4, 121.6)
        assert len(cache.get_all()) == 3
        assert cache.get_all()[2] == {"lat": 31.4, "lng": 121.6}

    def test_fifo_eviction(self):
        cache = TrajectoryCache(maxlen=3)
        cache.add(1, 1)
        cache.add(2, 2)
        cache.add(3, 3)
        cache.add(4, 4)  # 应移除 (1,1)
        points = cache.get_all()
        assert len(points) == 3
        assert points[0] == {"lat": 2, "lng": 2}
        assert points[-1] == {"lat": 4, "lng": 4}

    def test_clear(self):
        cache = TrajectoryCache(maxlen=2000)
        cache.add(31.2, 121.4)
        cache.add(31.3, 121.5)
        cache.clear()
        assert len(cache.get_all()) == 0

    def test_get_latest(self):
        cache = TrajectoryCache(maxlen=2000)
        assert cache.get_latest() is None
        cache.add(31.2, 121.4)
        cache.add(31.3, 121.5)
        latest = cache.get_latest()
        assert latest == {"lat": 31.3, "lng": 121.5}
