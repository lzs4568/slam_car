#!/usr/bin/env python3
"""
语义标注节点
============
接收标注请求 → 获取 GPS + map 坐标 → 写入语义数据库

标注来源:
  1. RViz2 Publish Point → /clicked_point (PointStamped)
  2. 语音标注 → /voice/annotation (String)
  3. 远程标注 → /annotation/remote (String, JSON)  — QT 前端右键地图
"""

import json
import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped, PoseStamped
from sensor_msgs.msg import NavSatFix
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener

from slam_car_bridge import semantic_db as db
from slam_car_bridge.embedding_client import EmbeddingClient


class AnnotationNode(Node):
    def __init__(self):
        super().__init__('annotation_node')

        # ---- 语义数据库 ----
        db.init_db()
        s = db.stats()
        self.get_logger().info(
            f"语义数据库: {s['db_path']} (地点{s['total']}个: "
            f"点{s['points']}, 区域{s['zones']})")

        # ---- 当前 GPS 位置 ----
        self._cur_lat = 0.0
        self._cur_lon = 0.0
        self._cur_alt = 0.0
        self._gps_valid = False
        self._gps_sub = self.create_subscription(
            NavSatFix, '/gps/fix', self._gps_cb, 10)

        # ---- TF (map→base_link) ----
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)
        self._cur_map_x = 0.0
        self._cur_map_y = 0.0

        # ---- 标注订阅 ----
        # RViz2 Publish Point
        self._click_sub = self.create_subscription(
            PointStamped, '/clicked_point', self._click_cb, 10)

        # 语音标注: "这里是三号楼" / "标记消防通道"
        self._voice_sub = self.create_subscription(
            String, '/voice/annotation', self._voice_cb, 10)

        # 远程标注: QT 前端右键地图 → JSON {name, lat, lng}
        self._remote_sub = self.create_subscription(
            String, '/annotation/remote', self._remote_cb, 10)

        # ---- 标注发布 (供前端显示) ----
        self._annotate_pub = self.create_publisher(
            String, '/annotation/status', 10)

        # ---- 语义 embedding ----
        self.declare_parameter('embedding_enabled', True)
        self.declare_parameter('embedding_api_key', '')
        self.declare_parameter('embedding_model', 'text-embedding-v2')

        self._embed_client = None
        if self.get_parameter('embedding_enabled').value:
            api_key = self.get_parameter('embedding_api_key').value
            if api_key:
                model = self.get_parameter('embedding_model').value
                self._embed_client = EmbeddingClient(api_key=api_key, model=model)
                self.get_logger().info(f"语义 embedding 启用: model={model}")

        self.get_logger().info("标注节点就绪 — 等待 /clicked_point 或 /voice/annotation")

    # ============================================================
    # GPS + TF 位置
    # ============================================================

    def _gps_cb(self, msg: NavSatFix):
        if math.isfinite(msg.latitude) and math.isfinite(msg.longitude):
            self._cur_lat = msg.latitude
            self._cur_lon = msg.longitude
            self._cur_alt = msg.altitude if math.isfinite(msg.altitude) else 0.0
            self._gps_valid = True

    def _generate_embedding(self, name: str) -> str:
        """生成地名 embedding，失败返回空串"""
        if not self._embed_client:
            return ""
        vec = self._embed_client.embed(name)
        if vec is not None:
            return json.dumps(vec)
        return ""

    def _update_map_position(self):
        """从 tf 获取当前 map 坐标"""
        try:
            now = rclpy.time.Time()
            trans = self._tf_buffer.lookup_transform(
                'map', 'base_link', now, timeout=rclpy.duration.Duration(seconds=1.0))
            self._cur_map_x = trans.transform.translation.x
            self._cur_map_y = trans.transform.translation.y
            return True
        except Exception:
            return False

    # ============================================================
    # RViz2 Publish Point 回调
    # ============================================================

    def _click_cb(self, msg: PointStamped):
        """收到 RViz2 点击 → 记录 map 坐标 + 当前 GPS"""
        map_x = msg.point.x
        map_y = msg.point.y
        gps_lat = self._cur_lat
        gps_lon = self._cur_lon

        self.get_logger().info(
            f"📌 RVIZ 点击: map=({map_x:.2f}, {map_y:.2f}) "
            f"gps=({gps_lat:.7f}, {gps_lon:.7f})")

        # 发布状态供 UI 消费
        msg_out = String()
        msg_out.data = f"clicked|{map_x:.2f},{map_y:.2f}|{gps_lat:.7f},{gps_lon:.7f}"
        self._annotate_pub.publish(msg_out)

    def _do_click_annotate(self, name: str, map_x: float, map_y: float,
                           gps_lat: float, gps_lon: float) -> int:
        """执行 RViz 点击标注"""
        aliases = _guess_aliases(name)
        embedding = self._generate_embedding(name)
        pid = db.add_place(
            name=name,
            gps_lat=gps_lat, gps_lon=gps_lon,
            map_x=map_x, map_y=map_y,
            aliases=aliases,
            place_type="point",
            embedding=embedding,
            created_by="rviz"
        )
        db.log_annotation("rviz", f"click at ({map_x:.2f},{map_y:.2f})", name, pid)
        self.get_logger().info(f"✅ 已标注: [{pid}] {name}")
        return pid

    # ============================================================
    # 语音标注回调
    # ============================================================

    def _voice_cb(self, msg: String):
        """收到语音标注指令: "这里是三号楼" """
        text = msg.data.strip()
        if not text:
            return
        self.get_logger().info(f"🎤 语音标注: {text}")

        # 从语音文本提取地名
        name = _extract_place_name(text)
        if not name:
            self._annotate_pub.publish(String(data="error|无法识别地名"))
            return

        # 获取当前位置
        self._update_map_position()
        map_x = self._cur_map_x
        map_y = self._cur_map_y
        gps_lat = self._cur_lat
        gps_lon = self._cur_lon

        self.get_logger().info(
            f"  地名={name}  map=({map_x:.2f},{map_y:.2f})  gps=({gps_lat:.7f},{gps_lon:.7f})")

        # 检查是否已存在
        existing = db.query_place(name)
        if existing:
            db.update_place(existing["id"],
                            gps_lat=gps_lat, gps_lon=gps_lon,
                            map_x=map_x, map_y=map_y)
            pid = existing["id"]
            action = "updated"
            self.get_logger().info(f"🔄 更新已有标注: [{pid}] {name}")
        else:
            aliases = _guess_aliases(name)
            embedding = self._generate_embedding(name)
            pid = db.add_place(
                name=name,
                gps_lat=gps_lat, gps_lon=gps_lon,
                map_x=map_x, map_y=map_y,
                aliases=aliases,
                embedding=embedding,
                created_by="voice"
            )
            action = "created"
            self.get_logger().info(f"✅ 语音标注: [{pid}] {name}")

        db.log_annotation("voice", text, name, pid)
        self._annotate_pub.publish(
            String(data=f"ok|{action}|[{pid}] {name}"))

    # ============================================================
    # 远程标注回调 (QT 前端右键地图)
    # ============================================================

    def _remote_cb(self, msg: String):
        """收到远程标注: {"name":"快递柜","lat":30.123,"lng":120.456}"""
        try:
            data = json.loads(msg.data)
            name = data.get("name", "").strip()
            lat = float(data.get("lat", 0))
            lng = float(data.get("lng", 0))
        except (json.JSONDecodeError, ValueError, TypeError):
            self.get_logger().warn(f"远程标注格式错误: {msg.data}")
            return

        if not name or (lat == 0.0 and lng == 0.0):
            self.get_logger().warn(f"远程标注缺少GPS坐标: name={name}")
            return

        self.get_logger().info(f"🖱️ 远程标注: {name} gps=({lat:.7f},{lng:.7f})")

        existing = db.query_place(name)
        if existing:
            db.update_place(existing["id"], gps_lat=lat, gps_lon=lng)
            pid = existing["id"]
            action = "updated"
            self.get_logger().info(f"🔄 更新已有标注: [{pid}] {name}")
        else:
            aliases = _guess_aliases(name)
            embedding = self._generate_embedding(name)
            pid = db.add_place(
                name=name,
                gps_lat=lat, gps_lon=lng,
                aliases=aliases,
                embedding=embedding,
                created_by="remote"
            )
            action = "created"
            self.get_logger().info(f"✅ 远程标注: [{pid}] {name}")

        db.log_annotation("remote", msg.data, name, pid)
        self._annotate_pub.publish(
            String(data=f"ok|{action}|[{pid}] {name}"))


# ============================================================
# 辅助函数
# ============================================================

def _extract_place_name(text: str) -> str:
    """从语音文本提取地名

    "这里是三号楼" → "三号楼"
    "标记这里是快递柜" → "快递柜"
    "记录快递柜" → "快递柜"
    """
    import re
    patterns = [
        r"这里是(.+)",
        r"标记.*?这里是(.+)",
        r"标记(.+)",
        r"记录(.+)",
        r"这是(.+)",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            name = m.group(1).strip()
            # 清理常见口语后缀
            name = re.sub(r"[了哦啊哈]$", "", name)
            if len(name) >= 1 and len(name) <= 20:
                return name

    # 兜底: 如果文本本身就像一个地名, 直接返回
    cleaned = re.sub(r"[的了哦啊哈]$", "", text.strip())
    if 1 <= len(cleaned) <= 10:
        return cleaned
    return ""


def _guess_aliases(name: str) -> str:
    """根据地名猜测别名"""
    aliases = {"三号楼": "3号楼,三栋", "四号楼": "4号楼,四栋",
               "大门": "入口,正门", "快递柜": "快递,丰巢,取快递",
               "水泵房": "泵房", "充电座": "充电桩,充电站",
               "消防通道": "消防车道", "架空层": "架空"}
    return aliases.get(name, "")


def main(args=None):
    rclpy.init(args=args)
    node = AnnotationNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
