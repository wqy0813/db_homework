# -*- coding: utf-8 -*-
"""测试基线侦察：收集关键数据，供 T1-T14 测试使用。"""
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

print("===== 关键巡演 =====")
for kw in ['周杰伦', '张学友', 'CBA', '排球', '猫', '莫奈', '郎朗', '只此青绿', '威尼斯商人']:
    r = q("SELECT series_id, series_name FROM show_series WHERE series_name LIKE %s", ('%%%s%%' % kw,))
    r2 = q("SELECT show_id, show_name, city_id FROM show_item WHERE show_name LIKE %s", ('%%%s%%' % kw,))
    print(kw, '| series:', r, '| shows:', r2[:5])

print("\n===== 用户 =====")
print(q("SELECT user_id, username, status FROM app_user"))
print("admin:", q("SELECT admin_id, username FROM admin"))

print("\n===== 城市/类型 =====")
print(q("SELECT city_id, city_name FROM city"))
print(q("SELECT category_id, category_name FROM category"))

print("\n===== 场馆（北京/武汉） =====")
print(q("SELECT venue_id, venue_name, city_id FROM venue WHERE city_id IN (1,2) ORDER BY venue_id"))

conn.close()
