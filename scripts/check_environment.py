# -*- coding: utf-8 -*-
"""Read-only environment/data consistency check for the ticket-sales project."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

import pymysql


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from config import DB_CONFIG  # noqa: E402


def run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(
            cmd, cwd=ROOT, stderr=subprocess.STDOUT, text=True
        ).strip()
    except Exception:
        return "unavailable"


def main() -> int:
    print("=" * 72)
    print("Ticket Sales 项目环境一致性检查（只读，不修改数据库）")
    print("=" * 72)

    print("\n[1] 项目代码")
    print(f"Git commit : {run(['git', 'rev-parse', '--short', 'HEAD'])}")
    status = run(["git", "status", "--short"])
    print("Working tree: " + ("CLEAN" if not status else "DIRTY"))
    if status:
        print(status)

    print("\n[2] 本机运行环境")
    print(f"OS         : {platform.platform()}")
    print(f"Python     : {platform.python_version()}")
    print(
        "DB target  : "
        f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )

    try:
        conn = pymysql.connect(
            **DB_CONFIG,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
        )
    except Exception as exc:
        print(f"\n[DB] CONNECTION FAILED: {exc}")
        return 2

    def scalar(sql: str):
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            return next(iter(row.values())) if row else None

    print("\n[3] 数据库版本")
    print(f"MySQL      : {scalar('SELECT VERSION()')}")
    print(f"DB now     : {scalar('SELECT NOW()')}")
    print(f"Event sched: {scalar('SELECT @@event_scheduler')}")

    print("\n[4] 定时 Event")
    event = None
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EVENT_NAME, STATUS, EVENT_TYPE, INTERVAL_VALUE,
                   INTERVAL_FIELD
            FROM information_schema.EVENTS
            WHERE EVENT_SCHEMA = DATABASE()
              AND EVENT_NAME = 'ev_session_status'
            """
        )
        event = cur.fetchone()

    if event:
        print(
            "ev_session_status: "
            f"status={event['STATUS']}, "
            f"every={event['INTERVAL_VALUE']} {event['INTERVAL_FIELD']}"
        )
    else:
        print("ev_session_status: MISSING")

    print("\n[5] 数据规模")
    tables = [
        "app_user",
        "show_session",
        "ticket_tier",
        "ticket_order",
        "order_item",
        "shipping_address",
        "attendee",
        "show_image",
    ]
    for table in tables:
        try:
            print(f"{table:20s}: {scalar(f'SELECT COUNT(*) FROM {table}')}")
        except Exception as exc:
            print(f"{table:20s}: ERROR ({exc})")

    print("\n[6] 核心脏数据检查")
    checks = [
        (
            "超场馆容量场次",
            """
            SELECT COUNT(*) FROM (
                SELECT se.session_id
                FROM show_session se
                JOIN venue v ON v.venue_id = se.venue_id
                JOIN ticket_tier t ON t.session_id = se.session_id
                GROUP BY se.session_id, v.capacity
                HAVING SUM(t.total_seats) > v.capacity
            ) x
            """,
        ),
        (
            "票档非法库存/销量",
            """
            SELECT COUNT(*)
            FROM ticket_tier
            WHERE price <= 0
               OR total_seats <= 0
               OR sold_seats < 0
               OR sold_seats > total_seats
            """,
        ),
        (
            "付款早于开售",
            """
            SELECT COUNT(*)
            FROM ticket_order o
            JOIN show_session se ON se.session_id = o.session_id
            WHERE o.order_status = 2
              AND o.pay_time IS NOT NULL
              AND o.pay_time < se.sale_start
            """,
        ),
        (
            "付款晚于开演",
            """
            SELECT COUNT(*)
            FROM ticket_order o
            JOIN show_session se ON se.session_id = o.session_id
            WHERE o.order_status = 2
              AND o.pay_time IS NOT NULL
              AND o.pay_time > se.show_time
            """,
        ),
        (
            "订单票数不在1~6",
            """
            SELECT COUNT(*)
            FROM ticket_order
            WHERE ticket_count < 1 OR ticket_count > 6
            """,
        ),
        (
            "已支付订单缺少付款时间",
            """
            SELECT COUNT(*)
            FROM ticket_order
            WHERE order_status = 2 AND pay_time IS NULL
            """,
        ),
        (
            "订单明细成交价非法",
            """
            SELECT COUNT(*)
            FROM order_item
            WHERE unit_price IS NULL OR unit_price <= 0
            """,
        ),
    ]
    for name, sql in checks:
        try:
            print(f"{name:24s}: {scalar(sql)}")
        except Exception as exc:
            print(f"{name:24s}: ERROR ({exc})")

    print("\n[7] 当前场次状态分布")
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT sale_status, COUNT(*) AS cnt
            FROM show_session
            GROUP BY sale_status
            ORDER BY sale_status
            """
        )
        for row in cur.fetchall():
            print(f"status={row['sale_status']}: {row['cnt']}")

    print("\n[8] 关键结构是否存在")
    structure_checks = [
        (
            "app_user.password_hash VARCHAR(255)",
            """
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'app_user'
              AND COLUMN_NAME = 'password_hash'
              AND DATA_TYPE = 'varchar'
              AND CHARACTER_MAXIMUM_LENGTH = 255
            """,
        ),
        (
            "show_session.sale_start",
            """
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'show_session'
              AND COLUMN_NAME = 'sale_start'
            """,
        ),
        (
            "order_item.unit_price",
            """
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'order_item'
              AND COLUMN_NAME = 'unit_price'
            """,
        ),
    ]
    for name, sql in structure_checks:
        print(f"{name:32s}: {'OK' if scalar(sql) else 'MISSING'}")

    conn.close()

    print("\n" + "=" * 72)
    print("请把这份完整输出原样发回；不要修改数字。")
    print("三个人都运行同一个脚本后，就能区分：")
    print("  代码问题 = Git commit 不同/代码工作区不同")
    print("  本机问题 = Git 相同，但数据库检查结果不同")
    print("  全组问题 = 三个人数据库检查结果相同")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
