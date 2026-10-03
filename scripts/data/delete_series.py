# -*- coding: utf-8 -*-
"""删除指定已故艺人的巡演（含订单/演出/场次/票档/系列）。
用法：python scripts/data/delete_series.py <series_id> [more_ids...]
"""
import os
import sys
import pymysql

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))
from config import DB_CONFIG  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print('用法: python scripts/data/delete_series.py <series_id> [more...]')
        return
    ids = [int(x) for x in sys.argv[1:]]
    ph = ','.join(['%s'] * len(ids))

    conn = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, autocommit=False, **DB_CONFIG)
    cur = conn.cursor()

    # 显示将删除的 series 和演出
    cur.execute("SELECT series_id, series_name FROM show_series WHERE series_id IN (%s)" % ph, ids)
    for r in cur.fetchall():
        print('将删除 series:', r['series_id'], r['series_name'])
    cur.execute("SELECT show_id FROM show_item WHERE series_id IN (%s)" % ph, ids)
    show_ids = [r['show_id'] for r in cur.fetchall()]
    print('涉及演出', len(show_ids), '场')

    # 删除订单（分批）
    if show_ids:
        sph = ','.join(['%s'] * len(show_ids))
        cur.execute("SELECT o.order_id FROM ticket_order o JOIN show_session se ON se.session_id=o.session_id "
                    "WHERE se.show_id IN (%s)" % sph, show_ids)
        oids = [r['order_id'] for r in cur.fetchall()]
        if oids:
            for i in range(0, len(oids), 5000):
                chunk = oids[i:i + 5000]
                oph = ','.join(['%s'] * len(chunk))
                cur.execute("DELETE FROM order_item WHERE order_id IN (%s)" % oph, chunk)
                cur.execute("DELETE FROM ticket_order WHERE order_id IN (%s)" % oph, chunk)
                conn.commit()
            print('已删订单', len(oids), '笔')
        cur.execute("DELETE FROM purchase_request WHERE session_id IN "
                    "(SELECT session_id FROM show_session WHERE show_id IN (%s))" % sph, show_ids)
        cur.execute("DELETE FROM show_item WHERE show_id IN (%s)" % sph, show_ids)
        conn.commit()
        print('已删演出', len(show_ids), '场')

    # 删除 series
    cur.execute("DELETE FROM show_series WHERE series_id IN (%s)" % ph, ids)
    conn.commit()
    print('已删 series', len(ids), '个')

    # 重建汇总
    cur.execute("TRUNCATE TABLE sales_daily")
    cur.execute("""INSERT INTO sales_daily(stat_date,order_count,ticket_count,total_amount)
                   SELECT DATE(pay_time), COUNT(*), SUM(ticket_count), SUM(total_amount)
                   FROM ticket_order WHERE order_status=2 AND pay_time IS NOT NULL GROUP BY DATE(pay_time)""")
    conn.commit()
    print('销售汇总已重建')
    conn.close()


if __name__ == '__main__':
    main()
