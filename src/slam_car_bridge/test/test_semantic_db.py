#!/usr/bin/env python3
"""Tests for semantic_db search_semantic() and embedding support"""

import json
import sys
import os
import unittest
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'slam_car_bridge'))

import semantic_db as db


class TestSearchSemantic(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        db.DB_DIR = self._tmpdir.name
        db.DB_PATH = os.path.join(self._tmpdir.name, "test_semantic.db")
        db.init_db()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _add_place_with_embedding(self, name: str, embedding: list, **kwargs):
        emb_str = json.dumps(embedding)
        return db.add_place(name=name, embedding=emb_str, **kwargs)

    def test_empty_db_returns_empty(self):
        """空库返回空列表"""
        self.assertEqual(db.search_semantic([0.1, 0.2, 0.3]), [])

    def test_no_embeddings_returns_empty(self):
        """所有地点都没有 embedding"""
        db.add_place(name="充电站", embedding="")
        db.add_place(name="快递柜", embedding="")
        self.assertEqual(db.search_semantic([0.1, 0.2, 0.3]), [])

    def test_exact_match_scores_one(self):
        """相同向量得分为 1.0"""
        emb = [0.1, 0.2, 0.3]
        self._add_place_with_embedding("快递柜", emb)
        result = db.search_semantic(emb, top_k=1, min_score=0.0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "快递柜")
        self.assertAlmostEqual(result[0]["score"], 1.0, places=5)

    def test_score_ordering_descending(self):
        """按相似度降序"""
        self._add_place_with_embedding("充电站", [1.0, 0.0, 0.0])
        self._add_place_with_embedding("快递柜", [0.1, 0.2, 0.3])
        self._add_place_with_embedding("三号楼", [0.5, 0.5, 0.0])
        result = db.search_semantic([0.1, 0.2, 0.3], top_k=3, min_score=0.0)
        self.assertGreaterEqual(len(result), 3)
        self.assertEqual(result[0]["name"], "快递柜")

    def test_min_score_filters_low_scores(self):
        """min_score 过滤低分"""
        self._add_place_with_embedding("充电站", [1.0, 0.0, 0.0])
        self._add_place_with_embedding("快递柜", [0.0, 1.0, 0.0])
        # query 与两者都正交 → 余弦相似度均为 0，被 min_score 过滤
        result = db.search_semantic([0.0, 0.0, 1.0], top_k=3, min_score=0.5)
        self.assertEqual(len(result), 0)

    def test_top_k_respected(self):
        """top_k 限制返回数量"""
        self._add_place_with_embedding("A", [1.0, 0.0])
        self._add_place_with_embedding("B", [0.9, 0.1])
        self._add_place_with_embedding("C", [0.8, 0.2])
        result = db.search_semantic([1.0, 0.0], top_k=2, min_score=0.0)
        self.assertEqual(len(result), 2)

    def test_add_place_stores_embedding(self):
        """add_place 带 embedding 参数能正确读写"""
        emb = [0.12, -0.34, 0.56]
        pid = db.add_place(name="测试", embedding=json.dumps(emb))
        place = db.get_place(pid)
        self.assertEqual(json.loads(place["embedding"]), emb)

    def test_add_place_default_empty_embedding(self):
        """不传 embedding 时默认为空串"""
        pid = db.add_place(name="无embedding")
        place = db.get_place(pid)
        self.assertEqual(place["embedding"], "")

    def test_corrupt_embedding_skipped(self):
        """损坏的 embedding 被跳过不影响其他结果"""
        db.add_place(name="A", embedding="not-valid-json")
        self._add_place_with_embedding("B", [0.1, 0.2])
        result = db.search_semantic([0.1, 0.2], top_k=3, min_score=0.0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "B")


if __name__ == '__main__':
    unittest.main()
