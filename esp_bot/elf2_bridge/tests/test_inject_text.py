import sys
import types
import threading

# ---- stub pipeline.py 顶部的重依赖 (本机无需真实安装) ----
for _m in ["serial", "pygame", "websocket", "dashscope"]:
    sys.modules.setdefault(_m, types.ModuleType(_m))
_audio = types.ModuleType("dashscope.audio")
_tts = types.ModuleType("dashscope.audio.tts_v2")
_tts.SpeechSynthesizer = object
_tts.AudioFormat = object
sys.modules.setdefault("dashscope.audio", _audio)
sys.modules.setdefault("dashscope.audio.tts_v2", _tts)

from pipeline import VoicePipeline


def _bare_pipeline():
    """跳过 __init__（不连串口/云），只装配 inject_text 需要的两个属性。"""
    p = VoicePipeline.__new__(VoicePipeline)
    p._sentence_queue = []
    p._sentence_cv = threading.Condition()
    return p


def test_inject_text_enqueues():
    p = _bare_pipeline()
    p.inject_text("去三号楼")
    assert p._sentence_queue == ["去三号楼"]


def test_inject_text_ignores_empty():
    p = _bare_pipeline()
    p.inject_text("")
    assert p._sentence_queue == []
