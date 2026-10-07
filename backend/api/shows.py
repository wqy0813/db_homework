# -*- coding: utf-8 -*-
"""演出浏览接口：列表筛选、详情（场次+票档）、城市/类型字典。"""
from flask import Blueprint, request

from db import q
from .helpers import ok

shows_bp = Blueprint('api_shows', __name__)


def _row(r):
    """把 datetime 等转成可序列化的基本类型。"""
    out = {}
    for k, v in r.items():
        if hasattr(v, 'isoformat'):
            out[k] = v.isoformat(sep=' ') if hasattr(v, 'hour') else v.isoformat()
        elif hasattr(v, 'as_integer_ratio'):  # Decimal
            out[k] = float(v)
        else:
            out[k] = v
    return out


@shows_bp.route('/dicts')
def dicts():
    cities = [_row(r) for r in q("SELECT * FROM city ORDER BY city_id")]
    cats = [_row(r) for r in q("SELECT * FROM category ORDER BY category_id")]
    return ok({'cities': cities, 'categories': cats})


@shows_bp.route('/shows')
def shows():
    city_id = request.args.get('city_id', type=int)
    cat_id = request.args.get('category_id', type=int)
    status = request.args.get('status', type=int)
    keyword = (request.args.get('keyword') or '').strip()
    sql = "SELECT * FROM v_show_list WHERE 1=1"
    args = []
    if city_id:
        sql += " AND city_id=%s"; args.append(city_id)
    if cat_id:
        sql += " AND category_id=%s"; args.append(cat_id)
    if status:
        sql += " AND show_status=%s"; args.append(status)
    if keyword:
        sql += " AND show_name LIKE %s"; args.append('%%%s%%' % keyword)
    sql += " ORDER BY show_id DESC"
    rows = [_row(r) for r in q(sql, args)]
    return ok({'list': rows, 'total': len(rows)})


@shows_bp.route('/shows/<int:show_id>')
def show_detail(show_id):
    show = q("""SELECT s.*, c.city_name, cat.category_name,
                      ser.poster_url AS series_poster_url
                FROM show_item s
                JOIN city c ON c.city_id=s.city_id
                JOIN category cat ON cat.category_id=s.category_id
                LEFT JOIN show_series ser ON ser.series_id=s.series_id
                WHERE s.show_id=%s""", (show_id,), one=True)
    if not show:
        return ok({'show': None, 'sessions': [], 'images': [], 'tiers': {}})
    if show.get('series_poster_url'):
        show['poster_url'] = show['series_poster_url']
    show.pop('series_poster_url', None)
    pr = q("SELECT min_price,max_price,show_status,show_dates FROM v_show_list WHERE show_id=%s",
           (show_id,), one=True) or {}
    images = [_row(r) for r in q(
        "SELECT * FROM show_image WHERE show_id=%s ORDER BY sort_no,image_id", (show_id,))]
    sessions = q("""SELECT se.session_id, se.show_id, se.venue_id,
                    se.show_time, se.sale_start,
                    se.sale_status,
                    v.venue_name, v.address,
                    (SELECT MIN(price) FROM ticket_tier t WHERE t.session_id=se.session_id) AS min_p,
                    (SELECT MAX(price) FROM ticket_tier t WHERE t.session_id=se.session_id) AS max_p
                    FROM show_session se JOIN venue v ON v.venue_id=se.venue_id
                    WHERE se.show_id=%s ORDER BY se.show_time""", (show_id,))
    tiers = q("""SELECT t.*, t.total_seats-t.sold_seats AS remain
                 FROM ticket_tier t
                 WHERE t.session_id IN (SELECT session_id FROM show_session WHERE show_id=%s)
                 ORDER BY t.session_id, t.price DESC""", (show_id,))
    tiers_by_session = {}
    for t in tiers:
        tiers_by_session.setdefault(t['session_id'], []).append(_row(t))
    data = {'show': _row(show), 'summary': _row(pr), 'images': images,
            'sessions': [_row(s) for s in sessions], 'tiers': tiers_by_session}
    return ok(data)


# ---------------------------------------------------------------------------
# 第 4 期：巡演/IP 聚合接口
# ---------------------------------------------------------------------------

@shows_bp.route('/series')
def series_list():
    """巡演列表（首页按巡演聚合展示）。"""
    city_id = request.args.get('city_id', type=int)
    cat_id = request.args.get('category_id', type=int)
    status = request.args.get('status', type=int)
    keyword = (request.args.get('keyword') or '').strip()

    sql = """
        SELECT ser.series_id, ser.series_name, ser.main_artist,
               ser.poster_url, ser.category_id, cat.category_name,
               COUNT(DISTINCT sh.show_id) AS station_count,
               COUNT(DISTINCT sh.city_id)  AS city_count,
               MIN(vl.min_price) AS min_price,
               MAX(vl.max_price) AS max_price,
               GROUP_CONCAT(DISTINCT DATE_FORMAT(se.show_time,'%%m.%%d')
                            ORDER BY se.show_time SEPARATOR ' / ') AS show_dates,
               MAX(ser.create_time) AS create_time,
               CASE
                 WHEN MAX(CASE WHEN vl.show_status=2 THEN 1 ELSE 0 END) > 0 THEN 2
                 WHEN MAX(CASE WHEN vl.show_status=1 THEN 1 ELSE 0 END) > 0 THEN 1
                 ELSE 3
               END AS status
        FROM show_series ser
        JOIN category cat ON cat.category_id=ser.category_id
        JOIN show_item sh ON sh.series_id=ser.series_id
        LEFT JOIN show_session se ON se.show_id=sh.show_id
        LEFT JOIN v_show_list vl ON vl.show_id=sh.show_id
        WHERE 1=1
    """
    args = []
    if city_id:
        sql += " AND EXISTS (SELECT 1 FROM show_item x WHERE x.series_id=ser.series_id AND x.city_id=%s)"
        args.append(city_id)
    if cat_id:
        sql += " AND ser.category_id=%s"; args.append(cat_id)
    if keyword:
        sql += " AND (ser.series_name LIKE %s OR ser.main_artist LIKE %s)"
        args += ['%%%s%%' % keyword, '%%%s%%' % keyword]
    sql += " GROUP BY ser.series_id, ser.series_name, ser.main_artist, ser.poster_url, ser.category_id, cat.category_name"
    if status:
        sql += " HAVING status=%s"; args.append(status)
    sql += " ORDER BY create_time DESC"

    rows = [_row(r) for r in q(sql, args)]
    return ok({'list': rows, 'total': len(rows)})


@shows_bp.route('/series/<int:series_id>')
def series_detail(series_id):
    """巡演详情：基本信息 + 各城市站（每站含场次日期、价格区间）。"""
    ser = q("""SELECT ser.*, cat.category_name
               FROM show_series ser JOIN category cat ON cat.category_id=ser.category_id
               WHERE ser.series_id=%s""", (series_id,), one=True)
    if not ser:
        return ok({'series': None, 'stations': []})
    stations = q("""
        SELECT sh.show_id, sh.city_id, c.city_name,
               COUNT(se.session_id) AS session_count,
               MIN(vl.min_price) AS min_price,
               MAX(vl.max_price) AS max_price,
               MAX(vl.show_status) AS show_status,
               GROUP_CONCAT(DISTINCT DATE_FORMAT(se.show_time,'%%m.%%d')
                            ORDER BY se.show_time SEPARATOR ' / ') AS show_dates,
               (SELECT MIN(se2.show_time) FROM show_session se2
                WHERE se2.show_id=sh.show_id) AS nearest_time
        FROM show_item sh
        JOIN city c ON c.city_id=sh.city_id
        LEFT JOIN show_session se ON se.show_id=sh.show_id
        LEFT JOIN v_show_list vl ON vl.show_id=sh.show_id
        WHERE sh.series_id=%s
        GROUP BY sh.show_id, sh.city_id, c.city_name
        ORDER BY c.city_id""", (series_id,))
    # 站的总价格区间（取该巡演各站 min/max 的全局区间）
    data = {'series': _row(ser), 'stations': [_row(s) for s in stations]}
    return ok(data)
