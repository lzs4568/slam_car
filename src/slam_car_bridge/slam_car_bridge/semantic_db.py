#!/usr/bin/env python3
"""
语义地图数据库
==============
SQLite 存储地点和区域标注，供语音导航和规则引擎使用。

数据库位置: ~/data/semantic/semantic.db
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Tuple

import numpy as np


DB_DIR = os.path.expanduser("~/data/semantic")
DB_PATH = os.path.join(DB_DIR, "semantic.db")


def _get_conn() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """建表 (幂等)"""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS places (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            aliases     TEXT DEFAULT '',
            place_type  TEXT DEFAULT 'point',
            gps_lat     REAL,
            gps_lon     REAL,
            gps_alt     REAL DEFAULT 0,
            map_x       REAL,
            map_y       REAL,
            polygon_json TEXT DEFAULT '',
            zone_type   TEXT DEFAULT '',
            extra       TEXT DEFAULT '{}',
            embedding   TEXT DEFAULT '',
            created_by  TEXT DEFAULT 'manual',
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            updated_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS annotation_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT DEFAULT 'manual',
            raw_text    TEXT DEFAULT '',
            parsed_name TEXT DEFAULT '',
            place_id    INTEGER,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    # Migration: add embedding column if upgrading from old schema
    try:
        conn.execute("ALTER TABLE places ADD COLUMN embedding TEXT DEFAULT ''")
    except Exception:
        pass
    conn.commit()
    conn.close()


# ============================================================
# 地点 CRUD
# ============================================================

def add_place(name: str, gps_lat: float = 0, gps_lon: float = 0, gps_alt: float = 0,
              map_x: float = 0, map_y: float = 0,
              aliases: str = "", place_type: str = "point",
              polygon_json: str = "", zone_type: str = "",
              created_by: str = "manual", extra: dict = None,
              embedding: str = "") -> int:
    """添加地点/区域，返回 id"""
    conn = _get_conn()
    cur = conn.execute("""
        INSERT INTO places (name, aliases, place_type, gps_lat, gps_lon, gps_alt,
                            map_x, map_y, polygon_json, zone_type, extra, embedding, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, aliases, place_type, gps_lat, gps_lon, gps_alt,
          map_x, map_y, polygon_json, zone_type,
          json.dumps(extra or {}, ensure_ascii=False), embedding, created_by))
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def update_place(place_id: int, **kwargs):
    """更新地点字段"""
    allowed = {"name", "aliases", "place_type", "gps_lat", "gps_lon", "gps_alt",
               "map_x", "map_y", "polygon_json", "zone_type", "extra", "embedding",
               "created_by"}
    sets = []
    vals = []
    for k, v in kwargs.items():
        if k in allowed:
            if k == "extra" and isinstance(v, dict):
                v = json.dumps(v, ensure_ascii=False)
            sets.append(f"{k}=?")
            vals.append(v)
    if not sets:
        return
    sets.append("updated_at=?")
    vals.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    vals.append(place_id)
    conn = _get_conn()
    conn.execute(f"UPDATE places SET {', '.join(sets)} WHERE id=?", vals)
    conn.commit()
    conn.close()


def query_place(name: str) -> Optional[dict]:
    """按名称模糊搜索 (支持别名)"""
    conn = _get_conn()
    pattern = f"%{name}%"
    row = conn.execute("""
        SELECT * FROM places
        WHERE name LIKE ? OR aliases LIKE ?
        ORDER BY
            CASE WHEN name = ? THEN 0 ELSE 1 END,
            id DESC
        LIMIT 1
    """, (pattern, pattern, name)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_place(place_id: int) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM places WHERE id=?", (place_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_all(place_type: str = "") -> List[dict]:
    """列出所有地点，可按类型过滤"""
    conn = _get_conn()
    if place_type:
        rows = conn.execute("SELECT * FROM places WHERE place_type=? ORDER BY id",
                            (place_type,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM places ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search(name: str) -> List[dict]:
    """模糊搜索"""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM places
        WHERE name LIKE ? OR aliases LIKE ?
        ORDER BY id
    """, (f"%{name}%", f"%{name}%")).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_place(place_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM places WHERE id=?", (place_id,))
    conn.commit()
    conn.close()


# ============================================================
# 标注日志
# ============================================================

def log_annotation(source: str, raw_text: str, parsed_name: str, place_id: int):
    conn = _get_conn()
    conn.execute("""
        INSERT INTO annotation_log (source, raw_text, parsed_name, place_id)
        VALUES (?, ?, ?, ?)
    """, (source, raw_text, parsed_name, place_id))
    conn.commit()
    conn.close()


def get_recent_annotations(limit: int = 20) -> List[dict]:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM annotation_log ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# 统计
# ============================================================

def stats() -> dict:
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM places").fetchone()[0]
    points = conn.execute(
        "SELECT COUNT(*) FROM places WHERE place_type='point'").fetchone()[0]
    zones = conn.execute(
        "SELECT COUNT(*) FROM places WHERE place_type='polygon'").fetchone()[0]
    conn.close()
    return {"total": total, "points": points, "zones": zones, "db_path": DB_PATH}


def search_semantic(query_vec: list, top_k: int = 3,
                    min_score: float = 0.7) -> list:
    """
    语义搜索 — 余弦相似度匹配。

    1. 读取所有 embedding 不为空的地点
    2. numpy 批量计算余弦相似度
    3. 按得分降序返回 top_k 条（score >= min_score）

    性能: <50 条记录 + 1024 维向量 < 1ms

    Returns:
        [{"id":3, "name":"快递柜", "score":0.93, "gps_lat":..., ...}, ...]
    """
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM places WHERE embedding != '' AND embedding IS NOT NULL"
    ).fetchall()
    conn.close()

    if not rows:
        return []

    query = np.array(query_vec, dtype=np.float64)
    results = []

    for row in rows:
        try:
            emb = np.array(json.loads(row["embedding"]), dtype=np.float64)
        except (json.JSONDecodeError, TypeError):
            continue
        if len(emb) != len(query):
            continue  # dimension mismatch (e.g. different embedding models)
        dot = np.dot(query, emb)
        norm_q = np.linalg.norm(query)
        norm_e = np.linalg.norm(emb)
        if norm_q == 0 or norm_e == 0:
            continue
        score = float(dot / (norm_q * norm_e))
        if score >= min_score:
            d = dict(row)
            d["score"] = score
            results.append(d)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


# 首次导入自动建表
init_db()
