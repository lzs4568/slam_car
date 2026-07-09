#!/usr/bin/env python3
"""
语义地点桥接节点
================
定期读取 semantic_db 中所有地点，以 JSON 推送到 ROS2 topic。
QT 前端订阅后在地图上渲染标注点，支持点击导航。

发布话题:
  /places/list   String (JSON)   1Hz 全量推送
"""

import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from slam_car_bridge import semantic_db as db


class PlacesBridge(Node):
    def __init__(self):
        super().__init__('places_bridge')
        self._pub = self.create_publisher(String, '/places/list', 10)
        self._timer = self.create_timer(1.0, self._publish_places)
        self.get_logger().info(f"地点桥接就绪 — {db.stats()['total']} 个地点")

    def _publish_places(self):
        places = db.list_all()
        slim = []
        for p in places:
            slim.append({
                "id": p["id"],
                "name": p["name"],
                "lat": p["gps_lat"] or 0.0,
                "lng": p["gps_lon"] or 0.0,
                "type": p["place_type"],
            })
        msg = String()
        msg.data = json.dumps(slim, ensure_ascii=False)
        self._pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = PlacesBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
