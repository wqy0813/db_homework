# -*- coding: utf-8 -*-
"""测试基线侦察（精简版）：关键巡演/演出/场次/票档/订单数据。"""
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

print("===== 5 个演示用户 =====")
print(q("SELECT user_id, username, status FROM app_user WHERE username IN ('zhang_san','li_si','wang_wu','zhao_liu','chen_qi')"))

print("\n===== 关键巡演 =====")
for kw in ['周杰伦', '张学友', '林俊杰', 'CBA', '排球', '猫', '莫奈', '郎朗', '只此青绿']:
    r = q("SELECT series_id, series_name, main_artist, category_id FROM show_series WHERE series_name LIKE %s", ('%%%s%%' % kw,))
    if r:
        for row in r:
            print(row)
    else:
        print('NOT FOUND:', kw)

print("\n===== 单场演出（威尼斯商人 等） =====")
r = q("SELECT show_id, show_name, city_id, series_id FROM show_item WHERE show_name LIKE %s", ('%%%s%%' % '威尼斯商人',))
for row in r:
    print(row)

print("\n===== 周杰伦巡演各站 =====")
r = q("""SELECT ser.series_id, sh.show_id, sh.show_name, c.city_name, sh.series_id
         FROM show_series ser JOIN show_item sh ON sh.series_id=ser.series_id
         JOIN city c ON c.city_id=sh.city_id
         WHERE ser.series_name LIKE %s ORDER BY sh.city_id""", ('%%周杰伦%%',))
for row in r:
    print(row)

print("\n===== 北京站（周杰伦）的场次与票档 =====")
r = q("""SELECT se.session_id, se.show_id, se.show_time, se.sale_start, se.sale_status, v.venue_name
         FROM show_session se JOIN venue v ON v.venue_id=se.venue_id
         WHERE se.show_id IN (SELECT show_id FROM show_item WHERE show_name LIKE %s AND city_id=1)
         ORDER BY se.show_time""", ('%%周杰伦%%',))
for row in r:
    print(row)
    t = q("""SELECT tier_id, tier_name, price, total_seats, sold_seats, total_seats-sold_seats AS remain
             FROM ticket_tier WHERE session_id=%s ORDER BY price DESC""", (row['session_id'],))
    for tt in t:
        print('   ', tt)

print("\n===== 预售场次示例 =====")
r = q("SELECT session_id, show_id, sale_status, sale_start FROM show_session WHERE sale_status=1 LIMIT 5")
for row in r:
    print(row)

print("\n===== 售罄票档示例 =====")
r = q("SELECT tier_id, tier_name, session_id, price, total_seats, sold_seats FROM ticket_tier WHERE total_seats-sold_seats=0 LIMIT 5")
for row in r:
    print(row)

print("\n===== 订单数据现状 =====")
r = q("SELECT order_status, COUNT(*) c FROM ticket_order GROUP BY order_status")
for row in r:
    print(row)
r = q("SELECT COUNT(*) c, MIN(pay_time) mn, MAX(pay_time) mx FROM ticket_order WHERE order_status=2")
print('paid orders:', r)

conn.close()
