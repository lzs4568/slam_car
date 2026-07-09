#!/usr/bin/env python3
"""
ROS2 语音桥接节点
=================
VoiceEventBus.on_asr → 指令匹配 → ROS2 发布

指令类型:
  标注:   "这里是<地名>"           → /voice/annotation
  导航:   "去<地名>"               → 查 semantic_db → GPS→ENU → /goal_pose
  移动:   "前进/后退/左转/右转/停车" → /cmd_vel
  其他:   交给 LLM 正常对话

依赖:
  elf2_bridge/pipeline.py — 需要 PYTHONPATH 包含 elf2_bridge 路径
  launch 文件中已自动设置
"""

import os
import sys
import math
import re
import time
import threading

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, PoseStamped
from sensor_msgs.msg import NavSatFix
from nav_msgs.msg import Odometry, Path
from std_msgs.msg import String

from slam_car_bridge import semantic_db as db
from slam_car_bridge.embedding_client import EmbeddingClient

# ---- pipeline 懒加载 (elf2_bridge 不在 slam_car_ws 里) ----
_pipeline_loaded = False
VoicePipeline = None

def _ensure_pipeline():
    """确保能导入 elf2_bridge 的 pipeline 模块"""
    global _pipeline_loaded, VoicePipeline
    if _pipeline_loaded:
        return
    # 尝试自动发现 elf2_bridge 路径
    candidates = [
        os.path.expanduser("~/elf2_bridge"),
        os.path.expanduser("~/data/elf2_bridge"),
        "/data/elf2_bridge",
        os.path.join(os.path.dirname(__file__), "../../../..", "esp_bot/elf2_bridge"),
    ]
    for p in candidates:
        p = os.path.abspath(p)
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)
    try:
        import pipeline
        global VoicePipeline
        VoicePipeline = pipeline.VoicePipeline
        _pipeline_loaded = True
    except ImportError:
        pass

try:
    from pymap3d import geodetic2enu
except ImportError:
    geodetic2enu = None


class Ros2VoiceBridge(Node):
    def __init__(self, voice_bus=None, cloud_services=None, audio_player=None):
        super().__init__('ros2_voice_bridge')

        self._bus = voice_bus
        self._cloud = cloud_services
        self._player = audio_player

        # ---- GPS 参考原点 ----
        self.declare_parameter('datum_lat', 0.0)
        self.declare_parameter('datum_lon', 0.0)
        self.declare_parameter('datum_alt', 0.0)
        self._datum_lat = self.get_parameter('datum_lat').value
        self._datum_lon = self.get_parameter('datum_lon').value
        self._datum_alt = self.get_parameter('datum_alt').value
        self._datum_set = (self._datum_lat != 0.0 and self._datum_lon != 0.0)

        self.declare_parameter('embedding_enabled', True)
        self.declare_parameter('embedding_api_key', '')
        self.declare_parameter('embedding_model', 'text-embedding-v2')
        self.declare_parameter('embedding_min_score', 0.7)

        self._gps_sub = self.create_subscription(
            NavSatFix, '/gps/fix', self._gps_cb, 10)

        # 里程计 — 用于距离控制
        self._cur_odom_x = 0.0
        self._cur_odom_y = 0.0
        self._odom_got_first = False
        self._odom_sub = self.create_subscription(
            Odometry, '/odometry/filtered', self._odom_cb, 10)

        # Nav2 状态检测 — /plan 最近2秒有更新 = Nav2在导航
        self._nav2_active = False
        self._nav2_last_plan_time = 0.0
        self._plan_sub = self.create_subscription(
            Path, '/plan', self._plan_cb, 10)

        # ---- 发布者 ----
        self._cmd_pub  = self.create_publisher(Twist, '/cmd_vel', 10)
        self._goal_pub = self.create_publisher(PoseStamped, '/goal_pose', 10)
        self._annotation_pub = self.create_publisher(String, '/voice/annotation', 10)

        # ---- 语义搜索 ----
        self._embed_client = None
        if self.get_parameter('embedding_enabled').value:
            api_key = self.get_parameter('embedding_api_key').value
            if api_key:
                model = self.get_parameter('embedding_model').value
                self._embed_client = EmbeddingClient(api_key=api_key, model=model)
                self.get_logger().info(f"语义搜索启用: model={model}")
            else:
                self.get_logger().info("语义搜索未启用 (api_key 为空)")

        # ---- 注册语音回调 ----
        if self._bus is not None:
            self._bus.on_asr(self._on_asr)

        self.get_logger().info(
            f"语音桥接就绪 {'(GPS参考已设)' if self._datum_set else '(等待GPS...)'} "
            f"地点数: {db.stats()['total']}")

    # ============================================================
    # GPS
    # ============================================================

    def _gps_cb(self, msg: NavSatFix):
        if self._datum_set:
            return
        if not (math.isfinite(msg.latitude) and math.isfinite(msg.longitude)):
            return
        self._datum_lat = msg.latitude
        self._datum_lon = msg.longitude
        self._datum_alt = msg.altitude if math.isfinite(msg.altitude) else 0.0
        self._datum_set = True
        self.get_logger().info(
            f"GPS 参考原点: lat={self._datum_lat:.8f} lon={self._datum_lon:.8f}")

    # ============================================================
    # 语音回调
    # ============================================================

    def _on_asr(self, text: str):
        self.get_logger().info(f"ASR: {text}")

        # 优先级: 标注 > 导航 > 移动
        if self._try_annotate(text):
            return
        if self._try_navigate(text):
            return
        if self._try_move(text):
            return

    # ============================================================
    # 标注指令
    # ============================================================

    def _try_annotate(self, text: str) -> bool:
        if any(kw in text for kw in ['这里是', '这是', '标记', '记录']):
            msg = String(data=text)
            self._annotation_pub.publish(msg)
            self.get_logger().info(f"→ 标注: {text}")
            self._speak("正在记录位置")
            return True
        return False

    # ============================================================
    # 导航指令: "去三号楼"
    # ============================================================

    def _try_navigate(self, text: str) -> bool:
        if '去' not in text:
            return False

        if not self._datum_set:
            self._speak("GPS未就绪，请稍后再试")
            return True

        if geodetic2enu is None:
            self._speak("导航模块未安装")
            return True

        # ---- 语义搜索 (优先) ----
        if self._embed_client is not None:
            vec = self._embed_client.embed(text)  # 用原始语音全文
            if vec is not None:
                min_score = self.get_parameter('embedding_min_score').value
                results = db.search_semantic(vec, top_k=1, min_score=min_score)
                if results:
                    place = results[0]
                    self.get_logger().info(
                        f"语义匹配: \"{text}\" → [{place['id']}] {place['name']} "
                        f"(score={place['score']:.2f})")
                    self._navigate_to_place(place)
                    return True

        # ---- LIKE 兜底 ----
        name = _extract_nav_target(text)
        if not name:
            return False

        place = db.query_place(name)
        if not place:
            self._speak(f"我还不知道{name}在哪，请先标注")
            return True

        self._navigate_to_place(place)
        return True

    def _navigate_to_place(self, place: dict):
        """GPS → ENU → 发布 /goal_pose。GPS 无效时返回 False。"""
        lat, lon = place['gps_lat'], place['gps_lon']
        if lat == 0 and lon == 0:
            name = place.get('name', 'unknown')
            self._speak(f"{name}的坐标还未设置")
            return False
        alt = place.get('gps_alt', 0)
        e, n, u = geodetic2enu(lat, lon, alt,
                               self._datum_lat, self._datum_lon, self._datum_alt)

        goal = PoseStamped()
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.header.frame_id = 'map'
        goal.pose.position.x = e
        goal.pose.position.y = n
        goal.pose.position.z = u
        goal.pose.orientation.w = 1.0

        self._goal_pub.publish(goal)
        name = place.get('name', 'unknown')
        self.get_logger().info(f"→ 导航: {name}  ENU e={e:.2f} n={n:.2f}")
        self._speak(f"好的，前往{name}")
        return True

    # ============================================================
    # 移动指令
    # ============================================================

    _move_thread: threading.Thread | None = None
    _move_stop = False
    _start_odom_x = 0.0
    _start_odom_y = 0.0

    def _odom_cb(self, msg):
        """记录最新里程计位置"""
        self._cur_odom_x = msg.pose.pose.position.x
        self._cur_odom_y = msg.pose.pose.position.y
        if not self._odom_got_first:
            self._odom_got_first = True
            self.get_logger().info(
                f"里程计已连接: x={self._cur_odom_x:.3f} y={self._cur_odom_y:.3f}")

    def _plan_cb(self, msg):
        """Nav2 /plan 有更新 → 说明正在自主导航"""
        self._nav2_last_plan_time = time.time()
        self._nav2_active = True

    def _is_nav2_running(self) -> bool:
        """如果最近2秒收到过 /plan, 认为 Nav2 在跑"""
        return (time.time() - self._nav2_last_plan_time) < 2.0

    def _distance_traveled(self) -> float:
        dx = self._cur_odom_x - self._start_odom_x
        dy = self._cur_odom_y - self._start_odom_y
        return math.sqrt(dx*dx + dy*dy)

    def _publish_move_until(self, twist: Twist, target_meters: float):
        """后台线程 20Hz 发 /cmd_vel, 走够 target_meters 后自动停"""
        if self._move_thread and self._move_thread.is_alive():
            self._move_stop = True
            self._move_thread.join(timeout=0.5)
        self._move_stop = False
        self._start_odom_x = self._cur_odom_x
        self._start_odom_y = self._cur_odom_y
        max_duration = 5.0  # 安全兜底: 最多5秒强制停
        elapsed = 0.0

        def _loop():
            nonlocal elapsed
            while not self._move_stop:
                self._cmd_pub.publish(twist)
                time.sleep(0.05)
                elapsed += 0.05
                if target_meters < 999 and self._distance_traveled() >= target_meters:
                    self.get_logger().info(f"→ 到达目标距离 {target_meters:.1f}米")
                    self._move_stop = True
                if elapsed >= max_duration:
                    self.get_logger().warn(f"→ 超时 {max_duration}秒, 强制停止")
                    self._move_stop = True
            for _ in range(4):
                self._cmd_pub.publish(Twist())
                time.sleep(0.05)

        self._move_thread = threading.Thread(target=_loop, daemon=True)
        self._move_thread.start()

    def _try_move(self, text: str) -> bool:
        twist = Twist()
        matched = False

        if any(kw in text for kw in ['停车', '停下', '停止', '停']):
            self._move_stop = True
            self._cmd_pub.publish(Twist())
            self.get_logger().info("→ 停车")
            return True

        # Nav2 自主导航中: 不允许手动移动 (会跟控制器打架)
        if self._is_nav2_running():
            self.get_logger().warn("Nav2 导航中, 忽略手动移动指令, 请说'停车'或'去<地点>'")
            return True  # 算匹配了, 但阻止执行

        # 解析距离: "前进两米" / "后退1米" / "前进500"
        dist = _extract_distance(text)

        if any(kw in text for kw in ['前进', '直走', '往前']):
            twist.linear.x = 0.2; matched = True
        elif any(kw in text for kw in ['后退', '往后', '倒车']):
            twist.linear.x = -0.15; matched = True
        elif any(kw in text for kw in ['左转', '向左']):
            twist.angular.z = 0.8; matched = True
        elif any(kw in text for kw in ['右转', '向右']):
            twist.angular.z = -0.8; matched = True

        if matched:
            if dist > 0 and twist.linear.x != 0:
                self.get_logger().info(
                    f"→ 移动 {dist}米: lin={twist.linear.x:.2f}")
                self._publish_move_until(twist, dist)
            elif twist.angular.z != 0:
                self.get_logger().info(f"→ 转向: ang={twist.angular.z:.2f}")
                # 转向默认转 90 度 (约 1.2 秒)
                self._publish_move_until(twist, target_meters=999)
            else:
                self.get_logger().info(f"→ 持续: lin={twist.linear.x:.2f}")
                self._publish_move_until(twist, target_meters=999)
            return True
        return False

    # ============================================================
    # TTS
    # ============================================================

    def _speak(self, text: str):
        if self._cloud is None or self._player is None:
            self.get_logger().warn(f"TTS不可用: {text}")
            return

        def _do():
            wav = self._cloud.tts(text)
            if wav:
                self._player.play_wav(wav)

        threading.Thread(target=_do, daemon=True).start()


# ============================================================
# 辅助
# ============================================================

def _extract_nav_target(text: str) -> str:
    m = re.search(r'去(.+?)(?:看看|一下|吧|吗|了)?$', text)
    if m:
        return m.group(1).strip()
    return ""


def _extract_distance(text: str) -> float:
    """从语音文本提取距离(米): '前进两米'→2.0, '后退1.5米'→1.5, '前进500'→0.5, '前进2米3'→2.0"""
    # 中文数字
    cn_map = {'一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
              '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '半': 0.5}
    # 阿拉伯数字: "1.5米" / "2米" / "500"
    m = re.search(r'(\d+\.?\d*)\s*米', text)
    if m:
        return float(m.group(1))
    # "前进500" → 0.5米 (毫米)
    m = re.search(r'(\d{3,4})\s*(?:$|。|\.|,|，)', text)
    if m:
        return float(m.group(1)) / 1000.0
    # 中文数字: "两米" / "一米五"
    for cn, val in cn_map.items():
        if cn + '米' in text:
            return float(val)
    m = re.search(r'([一二三四五六七八九])米([一二三四五六七八九半])', text)
    if m:
        return cn_map.get(m.group(1), 0) + cn_map.get(m.group(2), 0) * 0.1
    return 0.0


# ============================================================
# 独立入口 (测试用, 不连 pipeline)
# ============================================================

def main(args=None):
    rclpy.init(args=args)
    node = Ros2VoiceBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
