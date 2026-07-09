#!/usr/bin/env python3
"""Integration test: voice_bridge semantic search + LIKE fallback decision logic"""

import json
import sys
import os
import unittest
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'slam_car_bridge'))

import semantic_db as db


class TestNavigationDecisionLogic(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        db.DB_DIR = self._tmpdir.name
        db.DB_PATH = os.path.join(self._tmpdir.name, "test_integration.db")
        db.init_db()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_semantic_then_like_fallback(self):
        """语义搜索命中则返回，未命中则走 LIKE"""
        emb = [0.1, 0.2, 0.3, 0.4, 0.5]
        db.add_place(
            name="快递柜",
            gps_lat=30.123, gps_lon=120.456,
            aliases="快递,丰巢",
            embedding=json.dumps(emb),
        )

        # 语义搜索命中
        results = db.search_semantic(emb, top_k=1, min_score=0.7)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "快递柜")
        self.assertAlmostEqual(results[0]["score"], 1.0, places=5)

        # 语义搜索未命中（不同向量）
        results = db.search_semantic([-0.9, -0.8, -0.7, -0.6, -0.5],
                                     top_k=1, min_score=0.7)
        self.assertEqual(len(results), 0)

        # LIKE 兜底应能找到
        place = db.query_place("快递柜")
        self.assertIsNotNone(place)
        self.assertEqual(place["name"], "快递柜")

    def test_decide_route_semantic_hit(self):
        """模拟 _try_navigate 决策流程：语义命中"""
        emb_target = [1.0, 0.0, 0.0]
        db.add_place(name="充电站", gps_lat=30.1, gps_lon=120.1,
                     embedding=json.dumps(emb_target))

        query_emb = [0.99, 0.01, 0.0]  # 很接近
        results = db.search_semantic(query_emb, top_k=1, min_score=0.7)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "充电站")
        self.assertGreater(results[0]["score"], 0.99)

    def test_decide_route_semantic_miss_falls_back_to_like(self):
        """语义未命中 → LIKE 兜底"""
        db.add_place(name="三号楼", gps_lat=30.2, gps_lon=120.2,
                     aliases="3号楼,三栋")

        # 语义搜索
        query_emb = [0.1, 0.2, 0.3]
        results = db.search_semantic(query_emb, top_k=1, min_score=0.7)
        self.assertEqual(len(results), 0)

        # LIKE 兜底
        place = db.query_place("三号楼")
        self.assertIsNotNone(place)
        self.assertEqual(place["name"], "三号楼")


if __name__ == '__main__':
    unittest.main()
