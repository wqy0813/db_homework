# -*- coding: utf-8 -*-
"""管理员统计接口：时间段销售聚合（图表数据源）。"""
from datetime import date
from flask import Blueprint, request

from db import q
from .helpers import HIDDEN_CATEGORY_ID, ok, fail, require_login

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
    # 每日趋势和总计直接读取支付触发器维护的按日汇总，避免再次扫描订单表。
    daily_rows = q("""SELECT stat_date AS d, order_count AS orders,
                            ticket_count AS tickets, total_amount AS amount
                     FROM sales_daily WHERE stat_date BETWEEN %s AND %s
                     ORDER BY stat_date""", (start, end))

    # 类型、城市和热销榜共享一次订单范围扫描，再按演出结果在内存中汇总。
    dimensions = q("""SELECT s.show_id, s.show_name,
                            cat.category_id, cat.category_name,
                            c.city_id, c.city_name,
                            SUM(o.ticket_count) AS tickets,
                            SUM(o.total_amount) AS amount
                     FROM ticket_order o
                     JOIN show_session se ON se.session_id=o.session_id
                     JOIN show_item s ON s.show_id=se.show_id
                     JOIN category cat ON cat.category_id=s.category_id
                     JOIN venue v ON v.venue_id=se.venue_id
                     JOIN city c ON c.city_id=v.city_id
                     WHERE o.order_status=2 AND o.pay_time BETWEEN %s AND %s
                       AND s.category_id<>%s
                     GROUP BY s.show_id, s.show_name,
                              cat.category_id, cat.category_name,
                              c.city_id, c.city_name""",
                  (start, end_full, HIDDEN_CATEGORY_ID))

    cats_by_id = {}
    cities_by_id = {}
    top = []
    for row in dimensions:
        tickets = int(row['tickets'] or 0)
        amount = row['amount'] or 0
        category = cats_by_id.setdefault(row['category_id'], {
            'name': row['category_name'], 'tickets': 0, 'amount': 0,
        })
        category['tickets'] += tickets
        category['amount'] += amount

        city = cities_by_id.setdefault(row['city_id'], {
            'name': row['city_name'], 'tickets': 0, 'amount': 0,
        })
        city['tickets'] += tickets
        city['amount'] += amount

        top.append({
            'name': row['show_name'], 'city': row['city_name'],
            'tickets': tickets, 'amount': float(amount),
        })

    daily = [{'d': str(row['d']), 'orders': int(row['orders'] or 0),
              'tickets': int(row['tickets'] or 0), 'amount': float(row['amount'] or 0)}
             for row in daily_rows]
    total = {
        'orders': sum(int(row['orders'] or 0) for row in daily_rows),
        'tickets': sum(int(row['tickets'] or 0) for row in daily_rows),
        'amount': sum((row['amount'] or 0 for row in daily_rows), 0),
    }
    cats = sorted([{'name': row['name'], 'value': float(row['amount']),
                    'tickets': row['tickets']} for row in cats_by_id.values()],
                  key=lambda row: row['value'], reverse=True)
    cities = sorted([{'name': row['name'], 'tickets': row['tickets'],
                      'amount': float(row['amount'])} for row in cities_by_id.values()],
                    key=lambda row: row['amount'], reverse=True)
    top.sort(key=lambda row: row['tickets'], reverse=True)
    top = top[:10]
    return ok({
        'daily': daily,
        'cats': cats,
        'cities': cities,
        'top': top,
        'total': {'orders': total['orders'], 'tickets': total['tickets'],
                  'amount': float(total['amount'])},
    })
