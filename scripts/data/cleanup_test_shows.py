# -*- coding: utf-8 -*-
"""清理调试期残留的测试演出（名称含 日期调试/自动化测试/界面测试/调试 且无订单的）。"""
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

kws = ['日期调试', '自动化测试', '界面测试', '测试演出']
for kw in kws:
    rows = q("SELECT show_id, show_name FROM show_item WHERE show_name LIKE %s", ('%%%s%%' % kw,))
    for r in rows:
        # 有订单的不删（防止破坏销售数据）
        n = q("""SELECT COUNT(*) c FROM ticket_order o JOIN show_session se ON se.session_id=o.session_id
                 WHERE se.show_id=%s""", (r['show_id'],))[0]['c']
        if n == 0:
            cur.execute("DELETE FROM show_item WHERE show_id=%s", (r['show_id'],))
            conn.commit()
            print('deleted show_id=%s %s' % (r['show_id'], r['show_name']))
        else:
            print('SKIP (has orders) show_id=%s %s' % (r['show_id'], r['show_name']))
conn.close()
print('cleanup done')
