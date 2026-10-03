# -*- coding: utf-8 -*-
"""查询各系列(含演出数)与单场演出，为均衡脚本设计分组。"""
import sys, io
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

print("== 系列及其演出数(前40) ==")
rows = q("""SELECT sh.series_id, ser.series_name, COUNT(*) c
            FROM show_item sh JOIN show_series ser ON ser.series_id=sh.series_id
            GROUP BY sh.series_id, ser.series_name ORDER BY c DESC""")
total_series_shows = 0
for r in rows:
    total_series_shows += r['c']
    print('%4d  %-30s %s' % (r['c'], r['series_name'], r['series_id']))
print('系列数:', len(rows), '系列演出总数:', total_series_shows)

print("\n== 单场演出(series_id IS NULL)数 ==")
r = q("SELECT COUNT(*) c FROM show_item WHERE series_id IS NULL")
print('单场演出数:', r[0]['c'])

print("\n== 关键演示系列 ==")
for kw in ['周杰伦','张学友','林俊杰','CBA','排球','猫','莫奈','郎朗','只此青绿']:
    r = q("SELECT series_id, series_name FROM show_series WHERE series_name LIKE %s", ('%%%s%%' % kw,))
    for x in r:
        print(x)
conn.close()
