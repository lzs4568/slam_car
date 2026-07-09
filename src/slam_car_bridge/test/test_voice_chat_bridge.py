#!/usr/bin/env python3
"""Tests for voice_chat_bridge.build_chat_payload()"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'slam_car_bridge'))

import voice_chat_bridge


def test_build_chat_payload_user():
    s = voice_chat_bridge.build_chat_payload("user", "你好", 1783540798.9)
    obj = json.loads(s)
    assert obj["role"] == "user"
    assert obj["text"] == "你好"
    assert obj["ts"] == 1783540798  # 截断为整数秒


def test_build_chat_payload_keeps_chinese_unescaped():
    s = voice_chat_bridge.build_chat_payload("assistant", "温度正常", 0)
    assert "温度正常" in s  # ensure_ascii=False, 不转义中文
