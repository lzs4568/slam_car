#!/usr/bin/env python3
"""
阿里云 DashScope Text Embedding 客户端
=====================================
文字 → 向量，供语义搜索使用。

API: https://help.aliyun.com/document_detail/2712512.html

用法:
    client = EmbeddingClient(api_key="sk-xxx")
    vec = client.embed("这里是快递柜")
    # vec = [0.12, -0.34, ...] 或 None（失败时）
"""

import json
import urllib.request
import urllib.error
import socket
import logging

logger = logging.getLogger(__name__)

DASHSCOPE_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/embeddings/"
    "text-embedding/text-embedding"
)


class EmbeddingClient:
    """阿里云 DashScope text-embedding 封装。无状态、线程安全。"""

    def __init__(self, api_key: str, model: str = "text-embedding-v2",
                 timeout: float = 3.0):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    # ============================================================
    # 公开接口
    # ============================================================

    def embed(self, text: str) -> list | None:
        """
        将文本转为向量。失败返回 None，绝不抛异常。

        Args:
            text: 输入文本（空字符串或纯空白返回 None）

        Returns:
            list[float] 或 None
        """
        text = text.strip()
        if not text:
            logger.warning("embed() 收到空文本")
            return None

        request_body = {
            "model": self._model,
            "input": {
                "texts": [text]
            }
        }

        try:
            data = json.dumps(request_body).encode("utf-8")
            req = urllib.request.Request(
                DASHSCOPE_URL,
                data=data,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                embedding = body["output"]["embeddings"][0]["embedding"]
                return embedding

        except (urllib.error.HTTPError, urllib.error.URLError,
                socket.timeout, KeyError, IndexError, json.JSONDecodeError,
                Exception) as e:
            logger.warning(f"embed() 失败: {e}")
            return None

    def batch_embed(self, texts: list[str]) -> list:
        """
        批量生成向量。逐个调用 embed()，失败的条目对应 None。

        Args:
            texts: 文本列表

        Returns:
            list[list[float] | None] — 与输入等长
        """
        return [self.embed(t) for t in texts]
