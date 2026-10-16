# -*- coding: utf-8 -*-
"""修复测试数据异常脚本 (成员 1 任务 4)。

修复内容：
1. 修复付款时间早于开售时间的场次：将场次开售时间调整至首笔订单付款之前，保留所有真实订单、金额与付款时间。
2. 修复已到开售时间但仍标为预售的场次，更新为正确状态。
3. 清理演出介绍中的“满规模压测”等测试文案，替换为正式演示简介。
4. 检查并补全演出缺失的 series_id 巡演归属。
5. 核对修复前后的订单总数、已售票数与总销售额，保证业务数据不丢失、不重复。

用法：
  python scripts/data/fix_test_data.py --dry-run   # 仅预览将要修改的记录
  python scripts/data/fix_test_data.py             # 正式执行修复
"""
from __future__ import annotations

import argparse
import io
import os
import sys
from datetime import timedelta

import pymysql
from pymysql.cursors import DictCursor

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend"))
from config import DB_CONFIG  # noqa: E402


def check_and_fix(dry_run: bool = False):
    conn = pymysql.connect(cursorclass=DictCursor, **DB_CONFIG)
    cur = conn.cursor()

    print("=" * 60)
    print(f"开始检查并修复测试数据 (模式: {'DRY-RUN 预览' if dry_run else '正式执行'})")
    print("=" * 60)

    # -------------------------------------------------------------
    # 0. 初始业务指标核对
    # -------------------------------------------------------------
    cur.execute("SELECT COUNT(*) AS total_orders, COALESCE(SUM(ticket_count), 0) AS total_tickets, COALESCE(SUM(total_amount), 0) AS total_amount FROM ticket_order WHERE order_status = 2")
    metric_before = cur.fetchone()
    print(f"当前已支付订单统计: 订单数={metric_before['total_orders']}, 票数={metric_before['total_tickets']}, 总金额=¥{float(metric_before['total_amount']):.2f}")

    # -------------------------------------------------------------
    # 1. 付款时间早于开售时间的记录
    # -------------------------------------------------------------
    print("\n[检查项 1] 付款时间早于开售时间 (pay_time < sale_start):")
    cur.execute("""
        SELECT o.order_id, o.order_no, o.pay_time, se.session_id, se.show_time, se.sale_start
        FROM ticket_order o
        JOIN show_session se ON se.session_id = o.session_id
        WHERE o.order_status = 2 AND o.pay_time < se.sale_start
        ORDER BY se.session_id, o.pay_time
    """)
    early_orders = cur.fetchall()
    if not early_orders:
        print("  ✓ 无异常，所有已付款订单均在开售时间之后。")
    else:
        print(f"  发现 {len(early_orders)} 笔订单付款时间早于当前场次开售时间：")
        sessions_to_adjust = {}
        for o in early_orders:
            sid = o['session_id']
            if sid not in sessions_to_adjust or o['pay_time'] < sessions_to_adjust[sid]['min_pay']:
                sessions_to_adjust[sid] = {
                    'session_id': sid,
                    'current_sale_start': o['sale_start'],
                    'min_pay': o['pay_time'],
                    'show_time': o['show_time']
                }
            print(f"    - 订单 {o['order_no']} (ID {o['order_id']}): 付款时间 {o['pay_time']} < 场次 {sid} 开售时间 {o['sale_start']}")

        print(f"  修复方案：调整 {len(sessions_to_adjust)} 个场次的开售时间至订单付款前 2 小时，保留订单原始付款时间：")
        for sid, info in sessions_to_adjust.items():
            new_sale_start = info['min_pay'] - timedelta(hours=2)
            print(f"    - 场次 {sid}: 开售时间从 {info['current_sale_start']} 调整为 {new_sale_start}")
            if not dry_run:
                cur.execute("UPDATE show_session SET sale_start = %s WHERE session_id = %s", (new_sale_start, sid))

    # -------------------------------------------------------------
    # 2. 检查场次总票数超场馆容量
    # -------------------------------------------------------------
    print("\n[检查项 2] 场次总票数超场馆容量:")
    cur.execute("""
        SELECT se.session_id, s.show_name, v.venue_name, v.capacity, SUM(t.total_seats) AS allocated
        FROM show_session se
        JOIN show_item s ON s.show_id = se.show_id
        JOIN venue v ON v.venue_id = se.venue_id
        JOIN ticket_tier t ON t.session_id = se.session_id
        GROUP BY se.session_id, s.show_name, v.venue_name, v.capacity
        HAVING SUM(t.total_seats) > v.capacity
    """)
    over_capacity = cur.fetchall()
    if not over_capacity:
        print("  ✓ 无异常，所有场次分配总票数均未超过场馆容量。")
    else:
        print(f"  发现 {len(over_capacity)} 场演出总票数超过场馆容量：")
        for row in over_capacity:
            print(f"    - 场次 {row['session_id']} ({row['show_name']}): 场馆 {row['venue_name']} 容量 {row['capacity']}, 已分配 {row['allocated']}")

    # -------------------------------------------------------------
    # 3. 检查演出简介文案（清理“压测”字样）
    # -------------------------------------------------------------
    print("\n[检查项 3] 演出简介文案清理:")
    cur.execute("SELECT show_id, show_name, description FROM show_item WHERE description LIKE '%压测%'")
    stress_shows = cur.fetchall()
    if not stress_shows:
        print("  ✓ 无异常，演出简介中未包含“压测”等测试词汇。")
    else:
        print(f"  发现 {len(stress_shows)} 个演出简介包含“压测”字样：")
        for s in stress_shows:
            clean_desc = s['description'].replace('满规模压测生成数据。', '精彩呈现，欢迎购票。').replace('满规模压测', '全国巡演')
            print(f"    - 演出 {s['show_id']} ({s['show_name']}): 原简介『{s['description'][:40]}...』 -> 新简介『{clean_desc[:40]}...』")
            if not dry_run:
                cur.execute("UPDATE show_item SET description = %s WHERE show_id = %s", (clean_desc, s['show_id']))

    # -------------------------------------------------------------
    # 4. 补全 series_id 归属
    # -------------------------------------------------------------
    print("\n[检查项 4] 补全未归属巡演的演出 (series_id IS NULL):")
    from group_series import IP_KEYWORDS, CAT_POSTER
    cur.execute("SELECT series_id, series_name FROM show_series")
    series_cache = {s['series_name']: s['series_id'] for s in cur.fetchall()}

    cur.execute("SELECT show_id, show_name, category_id FROM show_item WHERE series_id IS NULL")
    orphan_shows = cur.fetchall()
    grouped_count = 0
    for kw, series_name, cat in IP_KEYWORDS:
        for r in orphan_shows:
            if kw in r['show_name']:
                if series_name not in series_cache:
                    if not dry_run:
                        cur.execute(
                            "INSERT INTO show_series(series_name,category_id,main_artist,poster_url,description) VALUES(%s,%s,%s,%s,%s)",
                            (series_name, cat, kw, CAT_POSTER.get(cat), series_name + '，全国巡演中。'))
                        series_cache[series_name] = cur.lastrowid
                    else:
                        series_cache[series_name] = -1
                print(f"    - 演出 {r['show_id']} ({r['show_name']}) -> 归入巡演: {series_name}")
                if not dry_run:
                    cur.execute("UPDATE show_item SET series_id=%s WHERE show_id=%s",
                                (series_cache[series_name], r['show_id']))
                grouped_count += 1
    if grouped_count == 0:
        print("  ✓ 无需补充，未归属演出的巡演关联已是最新状态。")
    else:
        print(f"  共归属 {grouped_count} 个演出至对应巡演。")

    # -------------------------------------------------------------
    # 5. 自动推进场次状态
    # -------------------------------------------------------------
    print("\n[检查项 5] 刷新场次售票状态至符合当前时间:")
    from api.session_status import refresh_sale_statuses
    if not dry_run:
        # 先提交前序修改，释放 show_session 行锁，避免 refresh_sale_statuses 开独立连接更新相同行时锁等待超时
        conn.commit()
        refresh_sale_statuses()
        print("  ✓ 状态刷新完成。")
        print("\n✓ 所有修复操作已成功提交至数据库！")
    else:
        print("  (DRY-RUN: 跳过状态刷新写入)")
        conn.rollback()
        print("\n[DRY-RUN 结束] 未对数据库做任何实际修改。")

    # -------------------------------------------------------------
    # 6. 最终指标核对
    # -------------------------------------------------------------
    cur.execute("SELECT COUNT(*) AS total_orders, COALESCE(SUM(ticket_count), 0) AS total_tickets, COALESCE(SUM(total_amount), 0) AS total_amount FROM ticket_order WHERE order_status = 2")
    metric_after = cur.fetchone()
    print("-" * 60)
    print("修复后指标核对:")
    print(f"  订单总数: {metric_before['total_orders']} -> {metric_after['total_orders']} (差异: {metric_after['total_orders'] - metric_before['total_orders']})")
    print(f"  售票总数: {metric_before['total_tickets']} -> {metric_after['total_tickets']} (差异: {metric_after['total_tickets'] - metric_before['total_tickets']})")
    print(f"  销售总额: ¥{float(metric_before['total_amount']):.2f} -> ¥{float(metric_after['total_amount']):.2f} (差异: ¥{float(metric_after['total_amount']) - float(metric_before['total_amount']):.2f})")
    print("-" * 60)

    conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="修复测试数据")
    parser.add_argument("--dry-run", action="store_true", help="预览变更但不写入数据库")
    args = parser.parse_args()
    check_and_fix(dry_run=args.dry_run)
