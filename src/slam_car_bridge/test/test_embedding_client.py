#!/usr/bin/env python3
"""Tests for embedding_client.py"""

import json
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'slam_car_bridge'))

from embedding_client import EmbeddingClient


class TestEmbeddingClient(unittest.TestCase):

    def test_embed_success(self):
        """正常调用返回向量列表"""
        mock_response = {
            "output": {
                "embeddings": [{"embedding": [0.1, 0.2, 0.3]}]
            }
        }
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = \
                json.dumps(mock_response).encode('utf-8')
            client = EmbeddingClient(api_key="test-key")
            result = client.embed("快递柜")
            self.assertEqual(result, [0.1, 0.2, 0.3])

    def test_embed_http_error_returns_none(self):
        """HTTP 错误返回 None，不抛异常"""
        from urllib.error import HTTPError
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = HTTPError(
                "https://dashscope.aliyuncs.com/", 401,
                "Unauthorized", {}, None)
            client = EmbeddingClient(api_key="bad-key")
            result = client.embed("测试")
            self.assertIsNone(result)

    def test_embed_timeout_returns_none(self):
        """超时返回 None，不抛异常"""
        import socket
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = socket.timeout("timed out")
            client = EmbeddingClient(api_key="test-key", timeout=0.1)
            result = client.embed("测试")
            self.assertIsNone(result)

    def test_embed_urllib_error_returns_none(self):
        """URLError 返回 None"""
        from urllib.error import URLError
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = URLError("connection refused")
            client = EmbeddingClient(api_key="test-key")
            result = client.embed("测试")
            self.assertIsNone(result)

    def test_embed_empty_text_returns_none(self):
        """空文本返回 None"""
        client = EmbeddingClient(api_key="test-key")
        self.assertIsNone(client.embed(""))
        self.assertIsNone(client.embed("   "))

    def test_embed_unexpected_response_returns_none(self):
        """API 返回格式异常时返回 None"""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = \
                b'{"unexpected": "format"}'
            client = EmbeddingClient(api_key="test-key")
            result = client.embed("测试")
            self.assertIsNone(result)

    def test_batch_embed_mixed_results(self):
        """批量调用，部分失败的对应 None"""
        mock_response_ok = {
            "output": {
                "embeddings": [{"embedding": [0.1, 0.2]}]
            }
        }
        from urllib.error import URLError
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_success = MagicMock()
            mock_success.__enter__.return_value.read.return_value = \
                json.dumps(mock_response_ok).encode('utf-8')
            mock_urlopen.side_effect = [mock_success, URLError("fail")]
            client = EmbeddingClient(api_key="test-key")
            results = client.batch_embed(["快递柜", "测试"])
            self.assertEqual(results[0], [0.1, 0.2])
            self.assertIsNone(results[1])
            self.assertEqual(len(results), 2)

    def test_init_defaults(self):
        """默认参数"""
        client = EmbeddingClient(api_key="test-key")
        self.assertEqual(client._model, "text-embedding-v2")
        self.assertEqual(client._timeout, 3.0)


if __name__ == '__main__':
    unittest.main()
