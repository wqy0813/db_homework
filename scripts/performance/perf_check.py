# -*- coding: utf-8 -*-
"""满规模性能实测：关键操作计时 + EXPLAIN 索引命中。运行：python perf_check.py"""
import os
import sys
import time

import pymysql

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))
from config import DB_CONFIG  # noqa

conn = pymysql.connect(autocommit=True, **DB_CONFIG)
cur = conn.cursor()


def t(label, sql, args=(), fetch=True):
    t0 = time.time()
    cur.execute(sql, args)
    rows = cur.fetchall() if fetch else None
    ms = (time.time() - t0) * 1000
    n = len(rows) if rows is not None else cur.rowcount
    print(f'  {ms:8.1f} ms   {label}  (返回/影响 {n} 行)')
    return rows


def explain(label, sql, args=()):
    cur.execute('EXPLAIN ' + sql, args)
    cols = [d[0] for d in cur.description]
    for r in cur.fetchall():
        d = dict(zip(cols, r))
        print(f'  [EXPLAIN] {label}: type={d.get("type")} key={d.get("key")} rows={d.get("rows")}')


print('=' * 70)
print('一、数据规模')
print('=' * 70)
for label, sql in [
    ('城市数', 'SELECT COUNT(*) FROM city'),
    ('用户数', 'SELECT COUNT(*) FROM app_user'),
    ('演出项目', 'SELECT COUNT(*) FROM show_item'),
    ('演出场次', 'SELECT COUNT(*) FROM show_session'),
    ('票档', 'SELECT COUNT(*) FROM ticket_tier'),
    ('订单', 'SELECT COUNT(*) FROM ticket_order'),
    ('售出票(明细)', 'SELECT COUNT(*) FROM order_item'),
    ('购票请求', 'SELECT COUNT(*) FROM purchase_request'),
]:
    cur.execute(sql); print(f'  {label:12s}: {cur.fetchone()[0]:,}')

print('=' * 70)
print('二、游客：列表 / 详情')
print('=' * 70)
t('演出列表(全量 v_show_list)', 'SELECT * FROM v_show_list')
t('列表按城市+类型筛选', 'SELECT * FROM v_show_list WHERE city_id=%s AND category_id=%s', (1, 1))
t('列表第 1 页(20条)', 'SELECT * FROM v_show_list ORDER BY show_id LIMIT 20')
t('列表第 50 页(OFFSET 980)', 'SELECT * FROM v_show_list ORDER BY show_id LIMIT 980,20')
explain('列表 city+cat 走索引', 'SELECT * FROM show_item WHERE city_id=1 AND category_id=1')
t('详情:某演出全部场次', 'SELECT * FROM show_session WHERE show_id=%s ORDER BY show_time', (100,))
t('详情:某场次票档余票', 'SELECT *, total_seats-sold_seats FROM ticket_tier WHERE session_id=%s', (500,))

print('=' * 70)
print('三、用户：登录 / 我的订单 / 购票扣减')
print('=' * 70)
t('10万用户中按用户名登录', 'SELECT user_id,username FROM app_user WHERE username=%s', ('f050000',))
explain('登录走唯一索引', 'SELECT user_id FROM app_user WHERE username=%s', ('f050000',))
cur.execute("SELECT user_id FROM ticket_order WHERE order_status=2 GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 1")
heavy_user = cur.fetchone()[0]
t(f'我的订单(用户 {heavy_user})', 'SELECT * FROM v_order_detail WHERE order_id IN (SELECT order_id FROM ticket_order WHERE user_id=%s) ORDER BY create_time DESC', (heavy_user,))
explain('我的订单走 (user_id,create_time)', 'SELECT order_id FROM ticket_order WHERE user_id=%s ORDER BY create_time DESC', (heavy_user,))

# 购票原子扣减（事务内，回滚不改动数据）
conn.autocommit(False)
t0 = time.time()
cur.execute("UPDATE ticket_tier SET sold_seats=sold_seats+2 WHERE tier_id=(SELECT tier_id FROM (SELECT tier_id FROM ticket_tier WHERE total_seats-sold_seats>=2 LIMIT 1) x) AND total_seats-sold_seats>=2")
print(f'  {(time.time()-t0)*1000:8.1f} ms   购票原子扣减余票(行锁)  影响 {cur.rowcount} 行')
conn.rollback(); conn.autocommit(True)

print('=' * 70)
print('四、管理员：时间段统计（图表数据源）')
print('=' * 70)
t('近一年按天销售聚合(折线)', """SELECT DATE(pay_time),COUNT(*),SUM(ticket_count),SUM(total_amount)
   FROM ticket_order WHERE order_status=2 AND pay_time BETWEEN %s AND %s GROUP BY DATE(pay_time)""",
  ('2025-09-01', '2026-12-31'))
explain('统计走 (order_status,pay_time)', 'SELECT 1 FROM ticket_order WHERE order_status=2 AND pay_time BETWEEN %s AND %s',
        ('2025-09-01', '2026-12-31'))
t('按类型统计(饼图)', """SELECT cat.category_name,SUM(o.ticket_count),SUM(o.total_amount)
   FROM ticket_order o JOIN show_session se ON se.session_id=o.session_id
   JOIN show_item s ON s.show_id=se.show_id JOIN category cat ON cat.category_id=s.category_id
   WHERE o.order_status=2 AND o.pay_time BETWEEN %s AND %s GROUP BY cat.category_id""",
  ('2025-09-01', '2026-12-31'))
t('按城市统计(柱图)', """SELECT c.city_name,SUM(o.ticket_count) FROM ticket_order o
   JOIN show_session se ON se.session_id=o.session_id JOIN venue v ON v.venue_id=se.venue_id
   JOIN city c ON c.city_id=v.city_id WHERE o.order_status=2 AND o.pay_time BETWEEN %s AND %s
   GROUP BY c.city_id,c.city_name""", ('2025-09-01', '2026-12-31'))
t('热销演出 TOP10', """SELECT s.show_name,SUM(o.ticket_count) FROM ticket_order o
   JOIN show_session se ON se.session_id=o.session_id JOIN show_item s ON s.show_id=se.show_id
   WHERE o.order_status=2 AND o.pay_time BETWEEN %s AND %s GROUP BY s.show_id,s.show_name
   ORDER BY 2 DESC LIMIT 10""", ('2025-09-01', '2026-12-31'))

print('=' * 70)
print('五、数据一致性')
print('=' * 70)
cur.execute("SELECT COUNT(*) FROM ticket_tier WHERE sold_seats>total_seats"); print('  超卖票档:', cur.fetchone()[0], '(应为0)')
cur.execute("""SELECT COUNT(*) FROM (SELECT attendee_id,session_id,COUNT(*) c FROM order_item
   GROUP BY attendee_id,session_id HAVING c>1) x"""); print('  限购重复:', cur.fetchone()[0], '(应为0)')
conn.close()
print('\n完成。')
