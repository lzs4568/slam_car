#!/usr/bin/env python3
"""
语义地点命令行管理工具
======================
用法:
  python3 places_cli.py list              # 列出所有地点
  python3 places_cli.py search <关键词>     # 搜索
  python3 places_cli.py add <名称> <lat> <lon> [别名]   # 手动添加
  python3 places_cli.py delete <id>        # 删除
  python3 places_cli.py show <id>          # 查看详情
  python3 places_cli.py stats             # 统计

示例:
  python3 places_cli.py add 三号楼 30.123456 120.654321 "3号楼,三栋"
  python3 places_cli.py search 快递
"""

import sys
import semantic_db as db


def cmd_list():
    places = db.list_all()
    if not places:
        print("(空 — 还没有标注地点)")
        return
    print(f"{'ID':<4} {'类型':<6} {'名称':<12} {'GPS':<26} {'来源':<8}")
    print("-" * 60)
    for p in places:
        t = "📍" if p["place_type"] == "point" else "🔲"
        gps = f"({p['gps_lat']:.7f}, {p['gps_lon']:.7f})"
        print(f"{p['id']:<4} {t:<6} {p['name']:<12} {gps:<26} {p['created_by']:<8}")


def cmd_search(name: str):
    results = db.search(name)
    if not results:
        print(f"未找到匹配 '{name}'")
        return
    for p in results:
        print(f"[{p['id']}] {p['name']}  ({p['gps_lat']:.7f}, {p['gps_lon']:.7f})  "
              f"别名: {p['aliases'] or '-'}  map=({p['map_x']:.2f},{p['map_y']:.2f})")


def cmd_add(name: str, lat: float, lon: float, aliases: str = ""):
    existing = db.query_place(name)
    if existing:
        db.update_place(existing["id"], gps_lat=lat, gps_lon=lon, aliases=aliases)
        print(f"🔄 已更新 [{existing['id']}] {name}")
    else:
        pid = db.add_place(name=name, gps_lat=lat, gps_lon=lon, aliases=aliases)
        print(f"✅ 已添加 [{pid}] {name}")


def cmd_delete(pid: int):
    p = db.get_place(pid)
    if not p:
        print(f"❌ 不存在: id={pid}")
        return
    db.delete_place(pid)
    print(f"🗑️ 已删除 [{pid}] {p['name']}")


def cmd_show(pid: int):
    p = db.get_place(pid)
    if not p:
        print(f"❌ 不存在: id={pid}")
        return
    print(f"ID:       {p['id']}")
    print(f"名称:     {p['name']}")
    print(f"别名:     {p['aliases'] or '-'}")
    print(f"类型:     {p['place_type']}")
    print(f"GPS:      {p['gps_lat']:.7f}, {p['gps_lon']:.7f}")
    print(f"Map:      ({p['map_x']:.2f}, {p['map_y']:.2f})")
    print(f"来源:     {p['created_by']}")
    print(f"创建时间: {p['created_at']}")


def cmd_stats():
    s = db.stats()
    print(f"数据库:   {s['db_path']}")
    print(f"地点总数: {s['total']}")
    print(f"  点:     {s['points']}")
    print(f"  区域:   {s['zones']}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == "list":
        cmd_list()
    elif cmd == "search" and len(sys.argv) >= 3:
        cmd_search(sys.argv[2])
    elif cmd == "add" and len(sys.argv) >= 5:
        cmd_add(sys.argv[2], float(sys.argv[3]), float(sys.argv[4]),
                sys.argv[5] if len(sys.argv) >= 6 else "")
    elif cmd == "delete" and len(sys.argv) >= 3:
        cmd_delete(int(sys.argv[2]))
    elif cmd == "show" and len(sys.argv) >= 3:
        cmd_show(int(sys.argv[2]))
    elif cmd == "stats":
        cmd_stats()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
