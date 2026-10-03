# -*- coding: utf-8 -*-
"""管理员统计接口：时间段销售聚合（图表数据源）。"""
from datetime import date
from flask import Blueprint, request

from db import q
from .helpers import ok, fail, require_login

stats_bp = Blueprint('api_stats', __name__)


@stats_bp.route('/admin/stats')
@require_login(role='admin')
def stats():
    start = request.args.get('start')
    end = request.args.get('end')
    if not start or not end:
        return fail('请提供开始和结束日期')
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except (TypeError, ValueError):
        return fail('日期格式必须为 YYYY-MM-DD')
    if start_date > end_date:
        return fail('开始日期不能晚于结束日期')
    start = start_date.isoformat()
    end = end_date.isoformat()
    end_full = end + ' 23:59:59'
    daily = q("""SELECT DATE(pay_time) AS d, COUNT(*) AS orders,
                        SUM(ticket_count) AS tickets, SUM(total_amount) AS amount
                 FROM ticket_order WHERE order_status=2 AND pay_time BETWEEN %s AND %s
                 GROUP BY DATE(pay_time) ORDER BY d""", (start, end_full))
    cats = q("""SELECT cat.category_name AS name,
                       SUM(o.ticket_count) AS tickets, SUM(o.total_amount) AS amount
                FROM ticket_order o
                JOIN show_session se ON se.session_id=o.session_id
                JOIN show_item s ON s.show_id=se.show_id
                JOIN category cat ON cat.category_id=s.category_id
                WHERE o.order_status=2 AND o.pay_time BETWEEN %s AND %s
                GROUP BY cat.category_id, cat.category_name ORDER BY amount DESC""",
             (start, end_full))
    cities = q("""SELECT c.city_name AS name,
                         SUM(o.ticket_count) AS tickets, SUM(o.total_amount) AS amount
                  FROM ticket_order o
                  JOIN show_session se ON se.session_id=o.session_id
                  JOIN venue v ON v.venue_id=se.venue_id
                  JOIN city c ON c.city_id=v.city_id
                  WHERE o.order_status=2 AND o.pay_time BETWEEN %s AND %s
                  GROUP BY c.city_id, c.city_name ORDER BY amount DESC""",
               (start, end_full))
    top = q("""SELECT s.show_name, c.city_name,
                      SUM(o.ticket_count) AS tickets, SUM(o.total_amount) AS amount
               FROM ticket_order o
               JOIN show_session se ON se.session_id=o.session_id
               JOIN show_item s ON s.show_id=se.show_id
               JOIN city c ON c.city_id=s.city_id
               WHERE o.order_status=2 AND o.pay_time BETWEEN %s AND %s
               GROUP BY s.show_id, s.show_name, c.city_name
               ORDER BY tickets DESC LIMIT 10""", (start, end_full))
    total = q("""SELECT COUNT(*) AS orders, COALESCE(SUM(ticket_count),0) AS tickets,
                        COALESCE(SUM(total_amount),0) AS amount
                 FROM ticket_order WHERE order_status=2 AND pay_time BETWEEN %s AND %s""",
              (start, end_full), one=True)
    return ok({
        'daily': [{'d': str(r['d']), 'tickets': int(r['tickets'] or 0),
                   'amount': float(r['amount'] or 0), 'orders': int(r['orders'] or 0)}
                  for r in daily],
        'cats': [{'name': r['name'], 'value': float(r['amount'] or 0),
                  'tickets': int(r['tickets'] or 0)} for r in cats],
        'cities': [{'name': r['name'], 'tickets': int(r['tickets'] or 0),
                    'amount': float(r['amount'] or 0)} for r in cities],
        'top': [{'name': r['show_name'], 'city': r['city_name'],
                 'tickets': int(r['tickets'] or 0), 'amount': float(r['amount'] or 0)}
                for r in top],
        'total': {'orders': int(total['orders'] or 0),
                  'tickets': int(total['tickets'] or 0),
                  'amount': float(total['amount'] or 0)},
    })
