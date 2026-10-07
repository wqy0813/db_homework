# -*- coding: utf-8 -*-
"""检查 show_status 分布与系列聚合状态。"""
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

print("== show_item 的 show_status 分布（v_show_list 口径） ==")
for r in q("SELECT show_status, COUNT(*) c FROM v_show_list GROUP BY show_status ORDER BY show_status"):
    print(r)

print("\n== show_session.sale_status 分布 ==")
session_counts = {r['sale_status']: r['c'] for r in q(
    "SELECT sale_status, COUNT(*) c FROM show_session GROUP BY sale_status")}
for status, count in sorted(session_counts.items()):
    label = {1: '预售中', 2: '售票中', 3: '售罄', 4: '已结束'}.get(status, '未知')
    print({'sale_status': status, 'status_name': label, 'count': count})
unavailable = session_counts.get(3, 0) + session_counts.get(4, 0)
distribution_ok = (session_counts.get(2, 0) < session_counts.get(1, 0) < unavailable)
print("数量顺序满足 售票中 < 预售中 < 售罄+已结束:", distribution_ok)
if not distribution_ok:
    print("注意：当前数据库的状态分布尚未满足目标顺序。")

print("\n== 系列聚合状态（与 /api/series 相同 SQL） ==")
rows = q("""
    SELECT st.status, COUNT(*) c FROM (
      SELECT CASE
        WHEN MAX(CASE WHEN vl.show_status=2 THEN 1 ELSE 0 END) > 0 THEN 2
        WHEN MAX(CASE WHEN vl.show_status=1 THEN 1 ELSE 0 END) > 0 THEN 1
        WHEN MAX(CASE WHEN vl.show_status=3 THEN 1 ELSE 0 END) > 0 THEN 3
        WHEN MAX(CASE WHEN vl.show_status=4 THEN 1 ELSE 0 END) > 0 THEN 4
        ELSE 3 END AS status
      FROM show_series ser
      JOIN show_item sh ON sh.series_id=ser.series_id
      LEFT JOIN v_show_list vl ON vl.show_id=sh.show_id
      GROUP BY ser.series_id
    ) st GROUP BY st.status ORDER BY st.status""")
for r in rows:
    print(r)

print("\n== 预售示例（show_status=1 的演出） ==")
for r in q("SELECT show_id, show_name, show_status FROM v_show_list WHERE show_status=1 LIMIT 5"):
    print(r)

print("\n== 售罄示例（show_status=3 的演出） ==")
for r in q("SELECT show_id, show_name, show_status FROM v_show_list WHERE show_status=3 LIMIT 5"):
    print(r)
conn.close()
if not distribution_ok:
    sys.exit(1)
