#!/usr/bin/env python3
"""
语音桥接主入口
==============
ESP32 USB CDC 音频 → 语音识别 → 通义千问 → 语音合成 → 播放

用法:
    python main.py                          # 自动检测串口
    python main.py --port /dev/ttyACM1      # 指定音频串口
    python main.py --vad 2                  # VAD 激进程度 0-3
    python main.py --no-history             # 每次独立对话（不保留上下文）

依赖:
    pip install -r requirements.txt
    export DASHSCOPE_API_KEY=sk-xxx         # 阿里云 DashScope API Key
    sudo usermod -a -G dialout $USER        # 串口权限（需重新登录）
"""

import os
import sys

# conda 环境隔离补丁：确保能找到 pip install --user 的包
sys.path.insert(0, os.path.expanduser("~/.local/lib/python3.10/site-packages"))
import glob
import argparse
import signal
import logging

from pipeline import VoicePipeline

logger = logging.getLogger("main")


def find_audio_port() -> str:
    """自动查找 ESP32 USB CDC 音频端口（优先 udev 绑定名）"""
    # 优先 udev 固定名
    if os.path.exists("/dev/esp32_audio"):
        return "/dev/esp32_audio"
    # 回退：自动检测
    for pat in ["/dev/ttyACM*", "/dev/ttyUSB*"]:
        ports = sorted(glob.glob(pat))
        if ports:
            acm = [p for p in ports if "ACM" in p]
            if acm:
                return acm[0]
            return ports[0]
    raise FileNotFoundError("未找到串口设备！请确认 ESP32 USB 已插入")


def main():
    parser = argparse.ArgumentParser(
        description="ELF2 语音桥接 — ESP32 音频 → 云端 ASR/LLM/TTS"
    )
    parser.add_argument("--port", "-p", default=None,
                        help="音频串口路径（默认自动检测）")
    parser.add_argument("--api-key", default=None,
                        help="DashScope API Key（默认读环境变量 DASHSCOPE_API_KEY）")
    parser.add_argument("--vad", type=int, default=1, choices=range(4),
                        help="VAD 激进程度 0-3 (0=安静, 1=适中, 2=偏激进, 3=嘈杂)")
    parser.add_argument("--no-history", action="store_true",
                        help="每次独立对话，不保留上下文")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()

    # 日志
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # API Key
    api_key = args.api_key or os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print("❌ 请设置 DashScope API Key：")
        print("   export DASHSCOPE_API_KEY=sk-xxx")
        print("   获取地址: https://dashscope.console.aliyun.com/apiKey")
        sys.exit(1)

    # 串口
    port = args.port or find_audio_port()
    print(f"🎤 音频串口: {port}")
    print(f"☁️  DashScope: {'✅' if api_key.startswith('sk-') else '⚠️'} 已配置")
    print("=" * 40)
    print("等待 ESP32 唤醒词 '小隆小隆'...")
    print("按 Ctrl+C 退出")
    print("=" * 40)

    # 启动管线
    pipeline = VoicePipeline(port, api_key)

    # 优雅退出
    def on_signal(sig, frame):
        logger.info("收到退出信号")
        pipeline.stop()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    pipeline.run()


if __name__ == "__main__":
    main()
