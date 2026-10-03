# -*- coding: utf-8 -*-
"""查 zhang_san 订单覆盖的场次/购票人，供购票测试挑选空闲数据。"""
import sys
import io
import os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymysql
from pymysql.cursors import DictCursor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))
from config import DB_CONFIG  # noqa: E402

conn = pymysql.connect(cursorclass=DictCursor, **DB_CONFIG)
cur = conn.cursor()

def q(sql, args=None):
    cur.execute(sql, args or ())
    return cur.fetchall()

print("== zhang_san(user_id=1) 的订单 ==")
rows = q("""SELECT o.order_id, o.order_no, o.session_id, o.tier_id, o.ticket_count, o.order_status,
                   se.show_id, s.show_name
            FROM ticket_order o JOIN show_session se ON se.session_id=o.session_id
            JOIN show_item s ON s.show_id=se.show_id
            WHERE o.user_id=1 ORDER BY o.order_id""")
for r in rows:
    print(r)

print("\n== 这些订单的购票人 ==")
rows = q("""SELECT oi.order_id, oi.session_id, oi.attendee_id, a.attendee_name, oi.unit_price
            FROM order_item oi JOIN attendee a ON a.attendee_id=oi.attendee_id
            WHERE oi.order_id IN (SELECT order_id FROM ticket_order WHERE user_id=1)""")
for r in rows:
    print(r)

print("\n== zhang_san 已购的 (attendee, session) 组合 ==")
rows = q("""SELECT oi.attendee_id, a.attendee_name, oi.session_id
            FROM order_item oi JOIN attendee a ON a.attendee_id=oi.attendee_id
            JOIN ticket_order o ON o.order_id=oi.order_id
            WHERE o.user_id=1 AND o.order_status IN (1,2)""")
for r in rows:
    print(r)

print("\n== 周杰伦北京站 session 1 各票档余票（再次确认） ==")
rows = q("SELECT tier_id, tier_name, price, total_seats, sold_seats FROM ticket_tier WHERE session_id=1 ORDER BY price DESC")
for r in rows:
    print(r)

conn.close()
