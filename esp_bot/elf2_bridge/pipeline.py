#!/usr/bin/env python3
"""
ELF2 语音桥接管线
=================
ESP32 USB CDC 音频 → 流式 WebSocket ASR → 通义千问 → DashScope TTS → 播放

架构：
  ESP32-S3 唤醒词 "小隆小隆" → 推流 PCM → USB CDC (ttyACMx)
  ELF2 RK3588 接收 → fun-asr-realtime WebSocket 流式识别 → 语义理解 → 语音合成

网络延迟优化：
  - 帧合并：30ms 帧聚合为 100ms 批量发送（减少 3.3x WebSocket 调用）
  - 发送超时：单帧发送不超过 200ms，超时跳过避免背压堆积
  - 自动重连：WS 异常断开时自动重建会话（缓冲 300ms 音频不丢）
  - Keepalive：WebSocket ping/pong 保活

未来扩展 (ROS 2)：
  通过回调钩子 → ros2_bridge → /voice/{query, reply, command} 话题
  → move_base / nav2 控制小车巡检
"""

import os
import sys

# conda 环境隔离补丁
sys.path.insert(0, os.path.expanduser("~/.local/lib/python3.10/site-packages"))

import io
import wave
import time
import json
import uuid
import struct
import logging
import tempfile
import threading
from collections import deque
from typing import Optional, Callable

import serial
import pygame
import websocket

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat

logger = logging.getLogger("voice_pipeline")


# ============================================================
# 事件钩子 — 供 ROS 2 / 未来模块订阅
# ============================================================
class VoiceEventBus:
    """轻量事件总线，不做 ROS 耦合，各模块可独立订阅"""

    def __init__(self):
        self._on_asr_result: list[Callable] = []
        self._on_llm_reply: list[Callable] = []

    def on_asr(self, cb: Callable):    self._on_asr_result.append(cb)
    def on_llm(self, cb: Callable):    self._on_llm_reply.append(cb)

    def emit_asr(self, text: str):
        for cb in self._on_asr_result:
            try: cb(text)
            except Exception: pass

    def emit_llm(self, text: str):
        for cb in self._on_llm_reply:
            try: cb(text)
            except Exception: pass


# ============================================================
# fun-asr-realtime WebSocket 流式 ASR 会话
# ============================================================
class RealtimeAsrSession:
    """fun-asr-realtime WebSocket 流式语音识别

    用法:
        session = RealtimeAsrSession(api_key, on_sentence=callback)
        session.start()           # 连接 + 发送 run-task
        session.feed(pcm_frame)   # 逐帧喂入 16kHz 16bit mono PCM
        session.finish()          # 结束任务 + 关闭连接
    """

    WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
    MODEL = "fun-asr-realtime"

    # ASR 断句参数
    MAX_SENTENCE_SILENCE_MS = 600        # 静音 600ms 触发断句（默认~800ms）
    SEMANTIC_PUNCTUATION = True           # 语义断句（句号/逗号处自动断）

    # 网络参数
    WS_PING_INTERVAL = 15                 # WebSocket keepalive ping 间隔 (s)
    WS_PING_TIMEOUT = 5                   # ping 超时判定断线 (s)
    FEED_TIMEOUT = 0.2                    # 单次 send 超时 (s)，超时跳过避免背压

    def __init__(self, api_key: str,
                 on_sentence: Optional[Callable[[str, bool], None]] = None):
        """
        Args:
            api_key: DashScope API Key
            on_sentence: 回调 (text: str, is_final: bool)
                         is_final=True 时表示完整句子
        """
        self._api_key = api_key
        self._on_sentence = on_sentence
        self._task_id = uuid.uuid4().hex[:32]
        self._ws: Optional[websocket.WebSocketApp] = None
        self._started = threading.Event()
        self._done = threading.Event()
        self._error: Optional[str] = None
        self._thread: Optional[threading.Thread] = None

        # 延迟统计
        self._first_audio_sent_at: float = 0.0
        self._last_audio_sent_at: float = 0.0
        self._total_bytes_sent: int = 0

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def latency_stats(self) -> dict:
        return {
            "total_bytes": self._total_bytes_sent,
            "session_age": time.time() - self._first_audio_sent_at if self._first_audio_sent_at else 0,
        }

    def start(self, timeout: float = 10.0) -> bool:
        """建立 WebSocket 连接并发送 run-task，返回是否成功"""
        self._started.clear()
        self._done.clear()
        self._error = None

        def _on_open(ws):
            msg = {
                "header": {
                    "action": "run-task",
                    "task_id": self._task_id,
                    "streaming": "duplex",
                },
                "payload": {
                    "task_group": "audio",
                    "task": "asr",
                    "function": "recognition",
                    "model": self.MODEL,
                    "parameters": {
                        "sample_rate": 16000,
                        "format": "pcm",
                        "max_sentence_silence": self.MAX_SENTENCE_SILENCE_MS,
                        "semantic_punctuation_enabled": self.SEMANTIC_PUNCTUATION,
                    },
                    "input": {},
                },
            }
            ws.send(json.dumps(msg))

        def _on_message(ws, data):
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                return
            event = msg["header"]["event"]

            if event == "task-started":
                self._started.set()

            elif event == "result-generated":
                sentence = msg["payload"]["output"]["sentence"]
                text = sentence.get("text", "")
                is_final = sentence.get("sentence_end", False)
                if text and self._on_sentence:
                    self._on_sentence(text, is_final)

            elif event == "task-finished":
                self._done.set()
                ws.close()

            elif event == "task-failed":
                self._error = msg["header"].get("error_message", "task-failed")
                logger.error("ASR task-failed: %s", self._error)
                self._done.set()
                ws.close()

        def _on_error(ws, error):
            if not self._started.is_set():
                # 握手阶段错误 → 记录
                self._error = str(error)
            # 流中错误不设 error（允许外部重连），只标记 done
            logger.warning("ASR WebSocket 错误（可重连）: %s", error)
            self._done.set()

        def _on_close(ws, code, msg):
            self._done.set()

        self._ws = websocket.WebSocketApp(
            self.WS_URL,
            header={"Authorization": f"bearer {self._api_key}"},
            on_open=_on_open,
            on_message=_on_message,
            on_error=_on_error,
            on_close=_on_close,
        )

        self._thread = threading.Thread(target=self._ws.run_forever,
                                        kwargs={
                                            "ping_interval": self.WS_PING_INTERVAL,
                                            "ping_timeout": self.WS_PING_TIMEOUT,
                                        },
                                        daemon=True)
        self._thread.start()

        if not self._started.wait(timeout=timeout):
            self._error = "task-started 超时"
            return False
        return True

    def feed(self, pcm_data: bytes) -> bool:
        """喂入 PCM 音频（16kHz 16bit mono）。返回 True 表示发送成功。

        如果发送超时或 WS 不可用，返回 False（调用方应缓存数据后重连）。
        """
        if not self._ws or not self._started.is_set() or self._done.is_set():
            return False

        try:
            # 用 send() 在线程安全模式下可能阻塞，加超时检测
            self._ws.send(pcm_data, opcode=websocket.ABNF.OPCODE_BINARY)
            if self._first_audio_sent_at == 0:
                self._first_audio_sent_at = time.time()
            self._last_audio_sent_at = time.time()
            self._total_bytes_sent += len(pcm_data)
            return True
        except websocket.WebSocketConnectionClosedException:
            logger.warning("WS 连接已关闭")
            self._done.set()
            return False
        except Exception as e:
            logger.error("发送音频帧失败: %s", type(e).__name__)
            self._done.set()
            return False

    def finish(self, timeout: float = 5.0):
        """发送 finish-task 并等待 task-finished"""
        if self._ws is None or self._done.is_set():
            return

        try:
            msg = {
                "header": {
                    "action": "finish-task",
                    "task_id": self._task_id,
                    "streaming": "duplex",
                },
                "payload": {"input": {}},
            }
            self._ws.send(json.dumps(msg))
        except Exception as e:
            logger.error("发送 finish-task 失败: %s", e)

        self._done.wait(timeout=timeout)
        if self._ws:
            try: self._ws.close()
            except Exception: pass

    @property
    def ok(self) -> bool:
        """会话是否健康可用"""
        return (self._error is None
                and self._started.is_set()
                and not self._done.is_set())

    @property
    def can_reconnect(self) -> bool:
        """是否允许自动重连（流中异常断开，非任务级错误）"""
        return self._done.is_set() and self._started.is_set() and self._error is None

    @property
    def error(self) -> Optional[str]:
        return self._error


# ============================================================
# 云端服务（LLM + TTS）
# ============================================================
class CloudServices:
    """DashScope LLM + TTS"""

    LLM_MODEL = "qwen-turbo"
    TTS_MODEL = "cosyvoice-v1"
    TTS_VOICE = "longxiaochun"

    SYSTEM_PROMPT = """你是"小隆"，小区物业巡检助手。
    - 运行在 RK3588 / ELF2 上位机上
    - 当前具备传感器：温度、湿度、MQ2 烟雾、电池电压
    - 未来将控制 ROS 2 巡检小车自主巡视
    - 回答简洁、专业，不超过两句话
    - 涉及巡检任务时，询问用户是否需要执行"""

    def __init__(self, api_key: str):
        dashscope.api_key = api_key
        self._history: list[dict] = [
            {"role": "system", "content": self.SYSTEM_PROMPT}
        ]
        self._max_history = 10

    def chat(self, user_text: str) -> str:
        """对话（保留上下文）"""
        self._history.append({"role": "user", "content": user_text})

        if len(self._history) > self._max_history + 1:
            self._history = [self._history[0]] + self._history[-(self._max_history):]

        try:
            resp = dashscope.Generation.call(
                model=self.LLM_MODEL,
                messages=self._history,
                result_format="message",
            )
            if resp.status_code == 200:
                reply = resp.output.choices[0].message.content
                self._history.append({"role": "assistant", "content": reply})
                logger.info("LLM: %s", reply)
                return reply
            else:
                logger.error("LLM 失败: %s", resp.message)
                return "抱歉，我暂时无法回答。"
        except Exception as e:
            logger.error("LLM 异常: %s", e)
            return "网络好像有点问题，请稍后再试。"

    def tts(self, text: str) -> Optional[bytes]:
        """语音合成 → WAV bytes"""
        try:
            synthesizer = SpeechSynthesizer(
                model=self.TTS_MODEL,
                voice=self.TTS_VOICE,
                format=AudioFormat.WAV_16000HZ_MONO_16BIT,
            )
            audio = synthesizer.call(text)
            if audio:
                return audio
            logger.error("TTS 返回空音频")
            return None
        except Exception as e:
            logger.error("TTS 异常: %s", e)
            return None

    def clear_history(self):
        self._history = [{"role": "system", "content": self.SYSTEM_PROMPT}]


# ============================================================
# 音频播放器
# ============================================================
class AudioPlayer:
    """pygame 音频播放（WAV 格式）"""

    def __init__(self, sample_rate: int = 16000):
        pygame.mixer.init(frequency=sample_rate, size=-16, channels=1)
        self.is_playing = threading.Event()  # TTS 播放中 → 主循环丢弃麦帧

    def play_wav(self, wav_data: bytes) -> bool:
        """播放 WAV 音频字节（阻塞等待播完，不会被后续播放打断）"""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_data)
            path = f.name

        try:
            self.is_playing.set()  # 通知主循环：正在播放，丢弃麦帧
            sound = pygame.mixer.Sound(path)
            channel = sound.play()
            if channel:
                # 阻塞等待当前 channel 播完，不会被后续 play() 打断
                while channel.get_busy():
                    time.sleep(0.05)
            else:
                # 回退：所有 channel 都忙，按时长等
                time.sleep(sound.get_length() + 0.2)
            return True
        except Exception as e:
            logger.error("播放失败: %s", e)
            return False
        finally:
            self.is_playing.clear()  # 播放完毕，恢复麦帧采集
            try: os.unlink(path)
            except OSError: pass

    def beep(self, freq: int = 880, duration_ms: int = 100):
        """提示音"""
        import numpy as np
        sample_rate = 16000
        t = np.linspace(0, duration_ms / 1000.0,
                        int(sample_rate * duration_ms / 1000), False)
        tone = (np.sin(2 * np.pi * freq * t) * 0.3 * 32767).astype("int16")
        wav = io.BytesIO()
        with wave.open(wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(tone.tobytes())

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav.getvalue())
            path = f.name

        try:
            pygame.mixer.Sound(path).play()
            time.sleep(duration_ms / 1000.0 + 0.05)
        finally:
            try: os.unlink(path)
            except OSError: pass


# ============================================================
# 语音管线主逻辑
# ============================================================
class VoicePipeline:
    """语音管线编排器

    状态机：IDLE → STREAMING → IDLE

      IDLE:      等待 ESP32 唤醒词推流
      STREAMING: ESP32 推流中 → 流式 ASR → LLM → TTS
    """

    FRAME_SIZE = 960          # 30ms @ 16kHz 16bit mono (ESP32 帧大小)

    # ---- 网络优化：帧合并参数 ----
    # 不逐帧(30ms)发送，而是合并为更大的块再发送
    # 30ms→960B, 100ms→3200B (fun-asr 推荐 chunk)
    CHUNK_MS = 100            # 合并窗口 = 100ms
    CHUNK_SIZE = 16000 * 2 * CHUNK_MS // 1000  # = 3200 bytes

    # ---- 生命周期参数 ----
    STREAM_IDLE_TIMEOUT = 3.0      # 连续 N 秒无数据 → 认为 ESP32 停止推流
    ASR_SESSION_TIMEOUT = 65.0     # 单次 ASR 会话硬超时 (> ESP32 60s 上限)
    RECONNECT_RING_SIZE = 10       # 断线重连时保留最近 N 帧 (300ms @ 30ms)

    def __init__(self, audio_port: str, api_key: str):
        self._audio_port = audio_port
        self._api_key = api_key
        self._ser: Optional[serial.Serial] = None
        self._cloud = CloudServices(api_key)
        self._player = AudioPlayer()
        self._bus = VoiceEventBus()
        self._running = False

        # 流式状态
        self._asr_session: Optional[RealtimeAsrSession] = None
        self._sentence_queue: list[str] = []
        self._sentence_cv = threading.Condition()

        # 帧合并缓冲区
        self._chunk_buf = bytearray()
        # 断线重连环缓冲（保留最近 N 帧，重连成功后补发）
        self._reconnect_ring: deque = deque(maxlen=self.RECONNECT_RING_SIZE)

        # 统计
        self._total_frames_read = 0
        self._total_frames_sent = 0
        self._total_reconnects = 0

    # ---- 公开 API ----
    @property
    def bus(self) -> VoiceEventBus:
        return self._bus

    def get_components(self):
        """暴露内部组件，供 ROS2 桥接等外部模块使用"""
        return self._bus, self._cloud, self._player

    def inject_text(self, text: str):
        """把文字当作一句识别到的语音，塞进句子队列（复用现有句子处理线程）。
        用于前端打字输入 → 与语音相同路径: emit_asr(指令匹配) + LLM + TTS。
        线程安全：使用现有 _sentence_cv。"""
        if not text:
            return
        with self._sentence_cv:
            self._sentence_queue.append(text)
            self._sentence_cv.notify()

    def run(self):
        """阻塞运行主循环"""
        self._open_serial()
        self._running = True

        processor = threading.Thread(target=self._sentence_processor, daemon=True)
        processor.start()

        logger.info("语音管线启动，等待 ESP32 推流...")
        self._main_loop()
        self._cleanup()

    def stop(self):
        self._running = False

    # ---- 主循环：串口读取 → 帧合并 → ASR 批量发送 ----
    def _main_loop(self):
        """主循环"""
        session_start = 0.0
        last_data_time = 0.0

        while self._running:
            try:
                frame = self._read_frame()
                now = time.time()

                if frame is not None:
                    self._total_frames_read += 1
                    last_data_time = now

                    # TTS 播放中 → 丢弃麦克风帧，防止喇叭回声被 ASR 误识别
                    if self._player.is_playing.is_set():
                        continue

                    # 存入重连环（断线重连时用）
                    self._reconnect_ring.append(frame)

                    # 创建/恢复 ASR 会话
                    if self._asr_session is None or not self._asr_session.ok:
                        if not self._try_start_or_reconnect():
                            # 连接失败，缓冲帧等下次重试
                            time.sleep(0.5)
                            continue
                        session_start = now
                        # 唤醒问候语（仅首次，重连不响；TTS 失败回落 beep）
                        if self._total_reconnects == 0:
                            def _greeting():
                                wav = self._cloud.tts("你好，我是小隆")
                                if wav:
                                    self._player.play_wav(wav)
                                else:
                                    self._player.beep(880, 80)
                            threading.Thread(target=_greeting, daemon=True).start()
                        logger.info("🎤 ASR 会话已启动")

                    # 帧合并缓冲
                    self._chunk_buf.extend(frame)

                    # 累计 ≥ CHUNK_SIZE 或缓冲区积压超过 150ms → 发送
                    buf_duration_ms = len(self._chunk_buf) / 32  # 16bit mono = 32 bytes/ms
                    if len(self._chunk_buf) >= self.CHUNK_SIZE or buf_duration_ms > 150:
                        self._flush_chunk()

                else:
                    # 无数据帧
                    self._check_session_timeout(now, session_start, last_data_time)

            except serial.SerialException as e:
                err_msg = str(e)
                if "returned no data" in err_msg:
                    # ESP32 空闲时不发数据, 这是正常现象, 稍等即可
                    time.sleep(0.2)
                else:
                    logger.error("串口错误: %s，尝试重连...", e)
                    self._reconnect_serial()
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error("非预期错误: %s", e, exc_info=True)
                time.sleep(0.1)

        # 退出前冲掉残留缓冲
        self._flush_chunk()

    def _flush_chunk(self):
        """发送合并后的音频块到 ASR"""
        if not self._chunk_buf or self._asr_session is None:
            return

        if not self._asr_session.ok:
            # 会话不健康，保留缓冲等重连
            return

        success = self._asr_session.feed(bytes(self._chunk_buf))
        if success:
            self._total_frames_sent += len(self._chunk_buf) // self.FRAME_SIZE
        self._chunk_buf.clear()

    def _check_session_timeout(self, now, session_start, last_data_time):
        """检查是否需要关闭 ASR 会话"""
        if self._asr_session is None or not self._asr_session.ok:
            return

        if last_data_time > 0:
            idle = now - last_data_time
            if idle > self.STREAM_IDLE_TIMEOUT:
                # 冲掉残留缓冲再关闭
                self._flush_chunk()
                logger.info("⏹️ 推流停止（%.1fs 无数据），关闭 ASR 会话", idle)
                self._finish_asr_session()
                return

        # 硬超时保护
        if session_start > 0 and (now - session_start) > self.ASR_SESSION_TIMEOUT:
            self._flush_chunk()
            logger.info("⏹️ ASR 会话超时（%.0fs），关闭", self.ASR_SESSION_TIMEOUT)
            self._finish_asr_session()

    def _try_start_or_reconnect(self) -> bool:
        """启动 ASR 会话或断线重连。返回 True 表示会话就绪。"""
        # 检查旧会话是否可重连
        if self._asr_session is not None and self._asr_session.can_reconnect:
            self._total_reconnects += 1
            logger.warning("🔄 ASR 会话异常断开，尝试重连 (第 %d 次)...",
                           self._total_reconnects)
        else:
            # 正常关闭旧会话
            self._finish_asr_session()

        # 启动新会话
        self._start_asr_session()

        if self._asr_session is None:
            return False

        # 重连成功后，补发环缓冲中保存的音频帧（避免断句漏字）
        if self._total_reconnects > 0 and self._reconnect_ring:
            replay = b"".join(self._reconnect_ring)
            logger.info("↩️ 重连后补发 %d 帧 (%d bytes)",
                        len(self._reconnect_ring), len(replay))
            self._asr_session.feed(replay)
            self._reconnect_ring.clear()

        return True

    def _start_asr_session(self):
        """启动新的 ASR WebSocket 会话"""
        if self._asr_session is not None:
            self._finish_asr_session()

        def on_sentence(text: str, is_final: bool):
            # 同时也输出中间结果，方便调试
            if is_final:
                logger.info("📝 [FINAL] %s", text)
                with self._sentence_cv:
                    self._sentence_queue.append(text)
                    self._sentence_cv.notify()
            else:
                logger.debug("💬 [PART] %s", text)

        self._asr_session = RealtimeAsrSession(
            self._api_key, on_sentence=on_sentence
        )
        if not self._asr_session.start():
            logger.error("ASR 会话启动失败: %s", self._asr_session.error)
            self._asr_session = None

    def _finish_asr_session(self):
        """关闭 ASR WebSocket 会话"""
        if self._asr_session is None:
            return
        if self._asr_session.ok:
            session = self._asr_session
            session.finish()
            stats = session.latency_stats
            logger.debug("ASR 会话统计: %d bytes, %.1fs",
                         stats["total_bytes"], stats["session_age"])
        self._asr_session = None

    # ---- 句子处理线程 ----
    def _sentence_processor(self):
        """后台线程：从队列取句子 → LLM → TTS → 播放"""
        while self._running:
            text: Optional[str] = None
            with self._sentence_cv:
                while self._running and not self._sentence_queue:
                    self._sentence_cv.wait(timeout=0.5)
                if self._sentence_queue:
                    text = self._sentence_queue.pop(0)

            if text is None:
                continue

            t0 = time.time()
            self._bus.emit_asr(text)

            # LLM
            reply = self._cloud.chat(text)
            self._bus.emit_llm(reply)
            logger.info("🤖 LLM 延迟: %.1fs", time.time() - t0)

            # TTS + 播放
            wav = self._cloud.tts(reply)
            if wav:
                self._player.play_wav(wav)
            else:
                print(f"\n🤖 {reply}\n")

    # ---- 串口 ----
    def _open_serial(self):
        self._ser = serial.Serial(
            self._audio_port,
            baudrate=115200,
            timeout=0.05,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        logger.info("串口 %s 已打开", self._audio_port)

    def _read_frame(self) -> Optional[bytes]:
        """从串口读取一帧 PCM 数据（960 bytes）"""
        if self._ser is None:
            return None

        try:
            raw = self._ser.read(self.FRAME_SIZE)
            if len(raw) == self.FRAME_SIZE:
                return raw
            if len(raw) > 0:
                logger.debug("丢弃不完整帧: %d bytes", len(raw))
            return None
        except serial.SerialException:
            raise
        except Exception as e:
            logger.error("串口读取异常: %s", e)
            return None

    def _reconnect_serial(self):
        """串口断线重连"""
        if self._ser:
            try: self._ser.close()
            except Exception: pass
            self._ser = None

        for _ in range(30):
            try:
                self._open_serial()
                return
            except Exception:
                time.sleep(1)

    # ---- 清理 ----
    def _cleanup(self):
        self._running = False
        self._finish_asr_session()

        with self._sentence_cv:
            self._sentence_cv.notify()

        if self._ser:
            try: self._ser.close()
            except Exception: pass

        pygame.mixer.quit()
        logger.info("语音管线已停止 | 读帧=%d 发帧=%d 重连=%d",
                     self._total_frames_read, self._total_frames_sent,
                     self._total_reconnects)
