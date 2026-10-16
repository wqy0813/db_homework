# -*- coding: utf-8 -*-
"""演出浏览接口：列表筛选、详情（场次+票档）、城市/类型字典。"""
from flask import Blueprint, request

from db import q
from posters import resolve_poster
from .helpers import HIDDEN_CATEGORY_ID, ok
from .session_status import refresh_sale_statuses

shows_bp = Blueprint('api_shows', __name__)


def _row(r):
    """把 datetime 等转成可序列化的基本类型。"""
    out = {}
    for k, v in r.items():
        if v is None:
            out[k] = None
        elif hasattr(v, 'isoformat'):
            out[k] = v.isoformat(sep=' ') if hasattr(v, 'hour') else v.isoformat()
        elif k.endswith('_id') or k in ('session_count', 'station_count', 'city_count', 'status', 'show_status', 'ticket_count'):
            try:
                out[k] = int(v)
            except (ValueError, TypeError):
                out[k] = v
        elif hasattr(v, 'as_integer_ratio'):  # Decimal
            out[k] = float(v)
        else:
            out[k] = v
    return out


def _poster_row(row):
    row = dict(row)
    row['poster_url'] = resolve_poster(
        row.get('series_name') or row.get('show_name'), row.get('category_id'),
        row.get('poster_url'), row.get('main_artist'))
    return _row(row)


@shows_bp.route('/dicts')
def dicts():
    cities = [_row(r) for r in q("SELECT * FROM city ORDER BY city_id")]
    cats = [_row(r) for r in q("SELECT * FROM category WHERE category_id<>%s ORDER BY category_id",
                               (HIDDEN_CATEGORY_ID,))]
    return ok({'cities': cities, 'categories': cats})


@shows_bp.route('/shows')
def shows():
    refresh_sale_statuses()
    city_id = request.args.get('city_id', type=int)
    cat_id = request.args.get('category_id', type=int)
    status = request.args.get('status', type=int)
    keyword = (request.args.get('keyword') or '').strip()
    sql = "SELECT * FROM v_show_list WHERE category_id<>%s"
    args = [HIDDEN_CATEGORY_ID]
    if city_id:
        sql += " AND city_id=%s"; args.append(city_id)
    if cat_id:
        sql += " AND category_id=%s"; args.append(cat_id)
    if status:
        sql += " AND show_status=%s"; args.append(status)
    if keyword:
        sql += " AND show_name LIKE %s"; args.append('%%%s%%' % keyword)
    sql += " ORDER BY show_id DESC"
    raw_rows = q(sql, args)
    # 正式关联的站点始终属于巡演，即使该巡演目前只有一个站点。
    # 未关联的旧批量数据则通过名称前缀和多站点数量识别。
    station_rows = q("SELECT show_id, series_id, show_name FROM show_item WHERE category_id<>%s",
                     (HIDDEN_CATEGORY_ID,))
    inferred_counts = {}
    for station in station_rows:
        if station['series_id'] is None and '·' in station['show_name']:
            prefix = station['show_name'].split('·', 1)[0].strip()
            if prefix:
                inferred_counts[prefix] = inferred_counts.get(prefix, 0) + 1
    rows = []
    for raw in raw_rows:
        row = dict(raw)
        prefix = row['show_name'].split('·', 1)[0].strip() if '·' in row['show_name'] else ''
        row['is_tour_station'] = bool(
            row.get('series_id') is not None
            or (row.get('series_id') is None and prefix and inferred_counts.get(prefix, 0) > 1)
        )
        rows.append(_poster_row(row))
    return ok({'list': rows, 'total': len(rows)})


@shows_bp.route('/shows/<int:show_id>')
def show_detail(show_id):
    show = q("""SELECT s.*, c.city_name, cat.category_name,
                      ser.poster_url AS series_poster_url,
                      ser.series_name, ser.main_artist
                FROM show_item s
                JOIN city c ON c.city_id=s.city_id
                JOIN category cat ON cat.category_id=s.category_id
                LEFT JOIN show_series ser ON ser.series_id=s.series_id
                WHERE s.show_id=%s AND s.category_id<>%s""", (show_id, HIDDEN_CATEGORY_ID), one=True)
    if not show:
        return ok({'show': None, 'sessions': [], 'images': [], 'tiers': {}})
    refresh_sale_statuses(show_id)
    show['poster_url'] = resolve_poster(
        show.get('series_name') or show['show_name'], show['category_id'],
        show.get('poster_url'), show.get('main_artist'))
    if show.get('series_poster_url') and not (show['poster_url'] or '').startswith(
            ('/posters/', '/static/img/uploads/', 'http://', 'https://')):
        show['poster_url'] = resolve_poster(
            show['series_name'], show['category_id'], show['series_poster_url'],
            show.get('main_artist'))
    show.pop('series_poster_url', None)
    pr = q("SELECT min_price,max_price,show_status,show_dates FROM v_show_list WHERE show_id=%s",
           (show_id,), one=True) or {}
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
    data = {'show': _row(show), 'summary': _row(pr), 'images': [],
            'sessions': [_row(s) for s in sessions], 'tiers': tiers_by_session}
    return ok(data)


# ---------------------------------------------------------------------------
# 第 4 期：巡演/IP 聚合接口
# ---------------------------------------------------------------------------

@shows_bp.route('/series')
def series_list():
    """巡演列表（首页按巡演聚合展示）。"""
    refresh_sale_statuses()
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
                 WHEN MAX(CASE WHEN vl.show_status=3 THEN 1 ELSE 0 END) > 0 THEN 3
                 WHEN MAX(CASE WHEN vl.show_status=4 THEN 1 ELSE 0 END) > 0 THEN 4
                 ELSE 3
               END AS status
        FROM show_series ser
        JOIN category cat ON cat.category_id=ser.category_id
        JOIN show_item sh ON sh.series_id=ser.series_id
        LEFT JOIN show_session se ON se.show_id=sh.show_id
        LEFT JOIN v_show_list vl ON vl.show_id=sh.show_id
        WHERE ser.category_id<>%s
    """
    args = [HIDDEN_CATEGORY_ID]
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

    rows = [_poster_row(r) for r in q(sql, args)]

    # 将尚未关联 show_series 的多站点数据按“·”之前的名称聚合为巡演。
    inferred_sql = """
        SELECT SUBSTRING_INDEX(sh.show_name,'·',1) AS series_name,
               SUBSTRING_INDEX(sh.show_name,'·',1) AS main_artist,
               MIN(sh.poster_url) AS poster_url,
               sh.category_id, cat.category_name,
               COUNT(DISTINCT sh.show_id) AS station_count,
               COUNT(DISTINCT sh.city_id) AS city_count,
               MIN(vl.min_price) AS min_price, MAX(vl.max_price) AS max_price,
               GROUP_CONCAT(DISTINCT DATE_FORMAT(se.show_time,'%%m.%%d')
                            ORDER BY se.show_time SEPARATOR ' / ') AS show_dates,
               MAX(sh.create_time) AS create_time,
               CASE
                 WHEN MAX(CASE WHEN vl.show_status=2 THEN 1 ELSE 0 END) > 0 THEN 2
                 WHEN MAX(CASE WHEN vl.show_status=1 THEN 1 ELSE 0 END) > 0 THEN 1
                 WHEN MAX(CASE WHEN vl.show_status=3 THEN 1 ELSE 0 END) > 0 THEN 3
                 WHEN MAX(CASE WHEN vl.show_status=4 THEN 1 ELSE 0 END) > 0 THEN 4
                 ELSE 3
               END AS status
        FROM show_item sh
        JOIN category cat ON cat.category_id=sh.category_id
        LEFT JOIN show_session se ON se.show_id=sh.show_id
        LEFT JOIN v_show_list vl ON vl.show_id=sh.show_id
        WHERE sh.series_id IS NULL AND sh.category_id<>%s AND sh.show_name LIKE '%%·%%'
    """
    inferred_args = [HIDDEN_CATEGORY_ID]
    if city_id:
        inferred_sql += " AND EXISTS (SELECT 1 FROM show_item x WHERE x.series_id IS NULL AND x.city_id=%s AND x.category_id=sh.category_id AND SUBSTRING_INDEX(x.show_name,'·',1)=SUBSTRING_INDEX(sh.show_name,'·',1))"
        inferred_args.append(city_id)
    if cat_id:
        inferred_sql += " AND sh.category_id=%s"; inferred_args.append(cat_id)
    if keyword:
        inferred_sql += " AND SUBSTRING_INDEX(sh.show_name,'·',1) LIKE %s"
        inferred_args.append('%%%s%%' % keyword)
    inferred_sql += " GROUP BY SUBSTRING_INDEX(sh.show_name,'·',1), sh.category_id, cat.category_name HAVING COUNT(DISTINCT sh.show_id)>1"
    inferred_rows = q(inferred_sql, inferred_args)
    for row in inferred_rows:
        row['series_id'] = None
        row['group_name'] = row['series_name']
        row['inferred'] = True
        if not status or row['status'] == status:
            rows.append(_poster_row(row))
    rows.sort(key=lambda row: row.get('create_time') or '', reverse=True)
    return ok({'list': rows, 'total': len(rows)})


@shows_bp.route('/series/group')
def inferred_series_detail():
    """按名称读取尚未关联 show_series 的巡演站点。"""
    refresh_sale_statuses()
    name = (request.args.get('name') or '').strip()
    if not name:
        return ok({'series': None, 'stations': []})
    stations = q("""
        SELECT vl.show_id, vl.city_id, vl.city_name,
               COUNT(DISTINCT se.session_id) AS session_count,
               MIN(vl.min_price) AS min_price, MAX(vl.max_price) AS max_price,
               CASE
                 WHEN MAX(CASE WHEN vl.show_status=2 THEN 1 ELSE 0 END) > 0 THEN 2
                 WHEN MAX(CASE WHEN vl.show_status=1 THEN 1 ELSE 0 END) > 0 THEN 1
                 WHEN MAX(CASE WHEN vl.show_status=3 THEN 1 ELSE 0 END) > 0 THEN 3
                 WHEN MAX(CASE WHEN vl.show_status=4 THEN 1 ELSE 0 END) > 0 THEN 4
                 ELSE 3
               END AS show_status,
               GROUP_CONCAT(DISTINCT DATE_FORMAT(se.show_time,'%%m.%%d')
                            ORDER BY se.show_time SEPARATOR ' / ') AS show_dates,
               MIN(se.show_time) AS nearest_time
        FROM show_item sh
        JOIN v_show_list vl ON vl.show_id=sh.show_id
        LEFT JOIN show_session se ON se.show_id=sh.show_id
        WHERE sh.series_id IS NULL AND sh.category_id<>%s
          AND SUBSTRING_INDEX(sh.show_name,'·',1)=%s
        GROUP BY vl.show_id, vl.city_id, vl.city_name
        ORDER BY vl.city_id, vl.show_id
    """, (HIDDEN_CATEGORY_ID, name))
    if len(stations) < 2:
        return ok({'series': None, 'stations': []})
    sample = q("""SELECT sh.category_id, cat.category_name, MIN(sh.poster_url) AS poster_url
                  FROM show_item sh JOIN category cat ON cat.category_id=sh.category_id
                  WHERE sh.series_id IS NULL AND sh.category_id<>%s
                    AND SUBSTRING_INDEX(sh.show_name,'·',1)=%s
                  GROUP BY sh.category_id, cat.category_name LIMIT 1""",
               (HIDDEN_CATEGORY_ID, name), one=True) or {}
    series = {'series_id': None, 'series_name': name, 'main_artist': name,
              'description': name, **sample}
    return ok({'series': _poster_row(series), 'stations': [_row(station) for station in stations]})


@shows_bp.route('/series/<int:series_id>')
def series_detail(series_id):
    """巡演详情：基本信息 + 各城市站（每站含场次日期、价格区间）。"""
    refresh_sale_statuses()
    ser = q("""SELECT ser.*, cat.category_name
               FROM show_series ser JOIN category cat ON cat.category_id=ser.category_id
               WHERE ser.series_id=%s AND ser.category_id<>%s""", (series_id, HIDDEN_CATEGORY_ID), one=True)
    if not ser:
        return ok({'series': None, 'stations': []})
    stations = q("""
        SELECT sh.show_id, sh.city_id, c.city_name,
               COUNT(se.session_id) AS session_count,
               MIN(vl.min_price) AS min_price,
               MAX(vl.max_price) AS max_price,
               CASE
                 WHEN MAX(CASE WHEN vl.show_status=2 THEN 1 ELSE 0 END) > 0 THEN 2
                 WHEN MAX(CASE WHEN vl.show_status=1 THEN 1 ELSE 0 END) > 0 THEN 1
                 WHEN MAX(CASE WHEN vl.show_status=3 THEN 1 ELSE 0 END) > 0 THEN 3
                 WHEN MAX(CASE WHEN vl.show_status=4 THEN 1 ELSE 0 END) > 0 THEN 4
                 ELSE 3
               END AS show_status,
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
    data = {'series': _poster_row(ser), 'stations': [_row(s) for s in stations]}
    return ok(data)
