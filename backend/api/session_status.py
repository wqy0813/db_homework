# -*- coding: utf-8 -*-
"""把存储的场次状态按当前售票时间和票档库存同步。"""
from datetime import datetime

from db import get_conn


def refresh_sale_statuses(show_id=None):
    """刷新全部场次，或只刷新指定演出的场次状态。"""
    conn = get_conn()
    now = datetime.now()
    try:
        with conn.cursor() as cur:
            sql = """SELECT se.session_id,se.show_id,se.show_time,se.sale_start,se.sale_status,
                            COUNT(t.tier_id) AS tier_count,
                            SUM(CASE WHEN t.tier_id IS NOT NULL
                                      AND t.sold_seats >= t.total_seats THEN 1 ELSE 0 END) AS sold_out_count
                     FROM show_session se
                     LEFT JOIN ticket_tier t ON t.session_id=se.session_id"""
            args = ()
            if show_id is not None:
                sql += " WHERE se.show_id=%s"
                args = (show_id,)
            sql += " GROUP BY se.session_id,se.show_id,se.show_time,se.sale_start,se.sale_status"
            cur.execute(sql, args)
            sessions = cur.fetchall()
            for session in sessions:
                if session['show_time'] <= now:
                    status = 4
                elif (session['tier_count'] and
                      session['sold_out_count'] == session['tier_count']):
                    status = 3
                else:
                    status = 2 if session['sale_start'] <= now else 1
                if int(session['sale_status']) != status:
                    cur.execute("UPDATE show_session SET sale_status=%s WHERE session_id=%s",
                                (status, session['session_id']))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
