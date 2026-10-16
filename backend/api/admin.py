# -*- coding: utf-8 -*-
"""管理员接口：演出/场次/票档的查询与增删改。"""
import os
from pathlib import Path
import re
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

import pymysql
from flask import Blueprint, current_app, request
from werkzeug.utils import secure_filename

from db import q, execute, get_conn
from posters import resolve_poster, COLLECT_DIR
from .helpers import HIDDEN_CATEGORY_ID, ok, fail, require_login, current_user
from .session_status import refresh_sale_statuses

admin_bp = Blueprint('api_admin', __name__)

_POSTER_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
_POSTER_MIMETYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}


def _parse_show_time(value):
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or '').strip().replace('T', ' ')
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def _parse_positive_price(value):
    try:
        price = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not price.is_finite() or price <= 0 or price > Decimal('999999.99'):
        return None
    try:
        quantized = price.quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError):
        return None
    if quantized <= Decimal('0.00'):
        return None
    return quantized


def _parse_positive_seats(value):
    if isinstance(value, bool):
        return None
    try:
        seats = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if isinstance(value, float) and value != seats:
        return None
    if isinstance(value, str) and value.strip() != str(seats):
        return None
    return seats if seats > 0 else None


def _sale_start_for(show_time, now):
    scheduled = show_time - timedelta(days=30)
    if scheduled < now:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    return scheduled


def _sale_status_for(show_time, sale_start, tiers, now):
    if show_time <= now:
        return 4
    if tiers and all(int(t['sold_seats']) >= int(t['total_seats']) for t in tiers):
        return 3
    return 2 if sale_start <= now else 1


def _has_image_signature(image, ext):
    """校验常见图片文件头，避免仅靠扩展名/MIME 接收任意文件。"""
    header = image.stream.read(12)
    image.stream.seek(0)
    signatures = {
        '.jpg': header.startswith(b'\xff\xd8\xff'),
        '.jpeg': header.startswith(b'\xff\xd8\xff'),
        '.png': header.startswith(b'\x89PNG\r\n\x1a\n'),
        '.gif': header[:6] in (b'GIF87a', b'GIF89a'),
        '.webp': header[:4] == b'RIFF' and header[8:12] == b'WEBP',
    }
    return signatures.get(ext, False)


def _validate_poster_url(url):
    """校验海报地址格式，拒绝 Windows 本地路径（如 C:\...、D:\...）、file:// 及含反斜杠的路径，并验证本地文件存在性。"""
    if not url:
        return True, ''
    url = str(url).strip()
    if not url:
        return True, ''
    if re.match(r'^[a-zA-Z]:[\\/]', url) or url.lower().startswith('file://') or '\\' in url:
        return False, '图片地址格式不正确：不能填写本地绝对路径（如 C:\\...），请先点击「选择并上传」或填写网络地址'
    if not url.startswith(('http://', 'https://', '/static/', '/posters/')):
        return False, '图片地址格式不正确：仅支持以 http://、https://、/static/ 或 /posters/ 开头的地址'
    if '..' in url.split('/'):
        return False, '图片地址不合法：包含非法相对路径'
    if url.startswith('/posters/'):
        parts = [p for p in url.split('/') if p]
        if len(parts) == 3 and parts[0] == 'posters' and parts[1] in 'ABCD':
            file_path = (COLLECT_DIR / parts[1] / parts[2]).resolve()
            try:
                file_path.relative_to((COLLECT_DIR / parts[1]).resolve())
            except ValueError:
                return False, '图片地址不合法'
            if file_path.suffix.lower() not in _POSTER_EXTENSIONS:
                return False, '海报图片格式不支持：仅支持常见图片格式'
            if not file_path.is_file():
                return False, '海报图片不存在：未找到对应的预设海报文件'
        else:
            return False, '海报图片不存在：未找到对应的预设海报文件'
    elif url.startswith('/static/'):
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        rel_path = url[len('/static/'):].lstrip('/')
        static_root = (Path(backend_dir) / 'static').resolve()
        file_path = (static_root / rel_path).resolve()
        try:
            file_path.relative_to(static_root)
        except ValueError:
            return False, '图片地址不合法：路径超出静态资源目录'
        if file_path.suffix.lower() not in _POSTER_EXTENSIONS:
            return False, '海报图片格式不支持：仅支持 jpg、jpeg、png、gif、webp 格式'
        if not file_path.is_file():
            return False, '海报图片不存在：未找到对应的本地静态图片资源'
    return True, url


@admin_bp.route('/admin/shows')
@require_login(role='admin')
def admin_shows():
    refresh_sale_statuses()
    conditions = []
    params = [HIDDEN_CATEGORY_ID]
    keyword = (request.args.get('keyword') or '').strip()
    category_id = request.args.get('category_id')
    city_id = request.args.get('city_id')
    show_status = request.args.get('show_status')
    if keyword:
        conditions.append("show_name LIKE %s")
        params.append('%' + keyword + '%')
    for value, column in ((category_id, 'category_id'), (city_id, 'city_id'),
                          (show_status, 'show_status')):
        if value:
            try:
                conditions.append(column + "=%s")
                params.append(int(value))
            except (TypeError, ValueError):
                return fail('筛选条件不正确')
    where = ''' WHERE category_id<>%s
                AND series_id IS NULL
                AND NOT (
                    series_id IS NULL AND show_name LIKE '%%·%%'
                    AND (SELECT COUNT(*) FROM show_item x
                         WHERE x.series_id IS NULL
                           AND x.category_id=v_show_list.category_id
                           AND SUBSTRING_INDEX(x.show_name,'·',1)=
                               SUBSTRING_INDEX(v_show_list.show_name,'·',1)) > 1
                )'''
    if conditions:
        where += ' AND ' + ' AND '.join(conditions)
    rows = q("SELECT * FROM v_show_list" + where + " ORDER BY show_id DESC", params)
    cities = q("SELECT * FROM city ORDER BY city_id")
    cats = q("SELECT * FROM category WHERE category_id<>%s ORDER BY category_id",
             (HIDDEN_CATEGORY_ID,))
    return ok({'list': [_s(r) for r in rows], 'cities': cities, 'categories': cats})


def _s(r):
    out = dict(r)
    if 'show_name' in out:
        out['poster_url'] = resolve_poster(
            out['show_name'], out.get('category_id'), out.get('poster_url'))
    for k, v in list(out.items()):
        if v is None:
            out[k] = None
        elif hasattr(v, 'isoformat'):
            out[k] = v.isoformat(sep=' ')
        elif k.endswith('_id') or k in ('session_count', 'station_count', 'city_count', 'status', 'show_status', 'ticket_count', 'total_seats', 'sold_seats', 'remain'):
            try:
                out[k] = int(v)
            except (ValueError, TypeError):
                out[k] = v
        elif hasattr(v, 'as_integer_ratio'):
            out[k] = float(v)
    return out


@admin_bp.route('/admin/shows/create', methods=['POST'])
@require_login(role='admin')
def create_show():
    b = request.get_json(silent=True) or request.form
    try:
        category_id = int(b.get('category_id'))
        if category_id == HIDDEN_CATEGORY_ID:
            return fail('该演出类型已停用')
        poster_ok, poster_val = _validate_poster_url(b.get('poster_url'))
        if not poster_ok:
            return fail(poster_val)
        sid = execute("""INSERT INTO show_item(show_name,category_id,city_id,poster_url,description,admin_id)
                         VALUES(%s,%s,%s,%s,%s,%s)""",
                      (b.get('show_name'), category_id, int(b.get('city_id')),
                       poster_val, b.get('description') or '', current_user()['id']))
        return ok({'show_id': sid}, msg='演出已创建')
    except Exception as e:
        return fail('创建失败：%s' % e)


@admin_bp.route('/admin/shows/<int:show_id>')
@require_login(role='admin')
def show_detail(show_id):
    refresh_sale_statuses(show_id)
    show = q("""SELECT s.*, c.city_name, cat.category_name
                FROM show_item s
                JOIN city c ON c.city_id=s.city_id
                JOIN category cat ON cat.category_id=s.category_id
                WHERE s.show_id=%s AND s.category_id<>%s""", (show_id, HIDDEN_CATEGORY_ID), one=True)
    if not show:
        return fail('演出不存在')
    sessions = q("""SELECT se.session_id, se.show_id, se.venue_id,
                           se.show_time, se.sale_start,
                           se.sale_status,
                           v.venue_name, v.capacity,
                           COALESCE((SELECT SUM(t.total_seats) FROM ticket_tier t
                                     WHERE t.session_id=se.session_id), 0) AS assigned_seats
                    FROM show_session se
                    JOIN venue v ON v.venue_id=se.venue_id
                    WHERE se.show_id=%s ORDER BY se.show_time""", (show_id,))
    tiers = q("""SELECT t.*, t.total_seats-t.sold_seats AS remain FROM ticket_tier t
                 WHERE t.session_id IN (SELECT session_id FROM show_session WHERE show_id=%s)
                 ORDER BY t.session_id, t.price DESC""", (show_id,))
    venues = q("SELECT * FROM venue WHERE city_id=%s ORDER BY venue_id", (show['city_id'],))
    tbs = {}
    for t in tiers:
        t['price'] = float(t['price'])
        tbs.setdefault(t['session_id'], []).append(t)
    return ok({'show': _s(show), 'sessions': [_s(x) for x in sessions],
               'tiers': tbs, 'venues': [_s(x) for x in venues]})


@admin_bp.route('/admin/shows/<int:show_id>/update', methods=['POST'])
@require_login(role='admin')
def update_show(show_id):
    b = request.get_json(silent=True) or request.form
    try:
        category_id = int(b.get('category_id'))
        if category_id == HIDDEN_CATEGORY_ID:
            return fail('该演出类型已停用')
        poster_ok, poster_val = _validate_poster_url(b.get('poster_url'))
        if not poster_ok:
            return fail(poster_val)
        target_city = int(b.get('city_id'))
        show = q("SELECT city_id,series_id,category_id FROM show_item WHERE show_id=%s", (show_id,), one=True)
        if not show:
            return fail('演出不存在')
        if show['series_id'] is not None:
            series = q("SELECT category_id FROM show_series WHERE series_id=%s",
                       (show['series_id'],), one=True)
            if series and category_id != series['category_id']:
                return fail('巡演站点类型必须与所属巡演一致')
        if show['city_id'] != target_city:
            session_count = q("SELECT COUNT(*) AS c FROM show_session WHERE show_id=%s",
                              (show_id,), one=True)['c']
            if session_count:
                return fail('该演出已有场次，不能直接更换城市；请先处理场次')
        execute("""UPDATE show_item SET show_name=%s,category_id=%s,city_id=%s,poster_url=%s,
                   description=%s,series_id=%s WHERE show_id=%s""",
                (b.get('show_name'), category_id, target_city,
                 poster_val, b.get('description') or '',
                 show['series_id'], show_id))
        return ok(msg='演出信息已更新')
    except (TypeError, ValueError):
        return fail('演出信息格式不正确')
    except Exception as e:
        return fail('更新失败：%s' % e)


@admin_bp.route('/admin/shows/<int:show_id>/delete', methods=['POST'])
@require_login(role='admin')
def delete_show(show_id):
    try:
        show = q("SELECT series_id FROM show_item WHERE show_id=%s", (show_id,), one=True)
        if not show:
            return fail('演出不存在')
        order_cnt = q("""SELECT COUNT(*) AS c FROM ticket_order o
                         JOIN show_session se ON se.session_id=o.session_id
                         WHERE se.show_id=%s""", (show_id,), one=True)['c']
        if order_cnt > 0:
            return fail('删除失败：该演出已有订单，为保留销售数据不可删除')
        series_id = show.get('series_id')
        if series_id is not None:
            return fail('该演出属于巡演，请在巡演管理中操作站点')
        execute("DELETE FROM show_item WHERE show_id=%s", (show_id,))
        return ok(msg='演出及其场次、票档、图片已级联删除')
    except pymysql.err.IntegrityError:
        return fail('删除失败：该演出已有订单，为保留销售数据不可删除')


# ---------------------------------------------------------------------------
# 巡演管理：巡演 → 站点（show_item）→ 场次（show_session）
# ---------------------------------------------------------------------------

@admin_bp.route('/admin/series')
@require_login(role='admin')
def admin_series():
    refresh_sale_statuses()
    keyword = (request.args.get('keyword') or '').strip()
    category_id = request.args.get('category_id')
    city_id = request.args.get('city_id')
    status = request.args.get('show_status')
    sql = """
        SELECT ser.series_id, ser.series_name, ser.main_artist, ser.poster_url,
               ser.category_id, cat.category_name, ser.description, ser.create_time,
               COUNT(DISTINCT sh.show_id) AS station_count,
               COUNT(DISTINCT sh.city_id) AS city_count,
               MIN(vl.min_price) AS min_price, MAX(vl.max_price) AS max_price,
               CASE
                 WHEN MAX(CASE WHEN vl.show_status=2 THEN 1 ELSE 0 END)>0 THEN 2
                 WHEN MAX(CASE WHEN vl.show_status=1 THEN 1 ELSE 0 END)>0 THEN 1
                 WHEN MAX(CASE WHEN vl.show_status=3 THEN 1 ELSE 0 END)>0 THEN 3
                 WHEN MAX(CASE WHEN vl.show_status=4 THEN 1 ELSE 0 END)>0 THEN 4
                 ELSE 3
               END AS show_status
        FROM show_series ser
        JOIN category cat ON cat.category_id=ser.category_id
        LEFT JOIN show_item sh ON sh.series_id=ser.series_id
        LEFT JOIN v_show_list vl ON vl.show_id=sh.show_id
        WHERE ser.category_id<>%s
    """
    args = [HIDDEN_CATEGORY_ID]
    if keyword:
        sql += " AND (ser.series_name LIKE %s OR ser.main_artist LIKE %s)"
        args.extend(['%%%s%%' % keyword, '%%%s%%' % keyword])
    if category_id:
        try:
            sql += " AND ser.category_id=%s"; args.append(int(category_id))
        except (TypeError, ValueError):
            return fail('类型筛选条件不正确')
    if city_id:
        try:
            sql += " AND EXISTS (SELECT 1 FROM show_item sx WHERE sx.series_id=ser.series_id AND sx.city_id=%s)"
            args.append(int(city_id))
        except (TypeError, ValueError):
            return fail('城市筛选条件不正确')
    sql += " GROUP BY ser.series_id, ser.series_name, ser.main_artist, ser.poster_url, ser.category_id, cat.category_name, ser.description, ser.create_time"
    if status:
        try:
            sql += " HAVING show_status=%s"; args.append(int(status))
        except (TypeError, ValueError):
            return fail('状态筛选条件不正确')
    sql += " ORDER BY ser.create_time DESC, ser.series_id DESC"
    rows = [_s(row) for row in q(sql, args)]
    for row in rows:
        row['poster_url'] = resolve_poster(row['series_name'], row.get('category_id'),
                                           row.get('poster_url'), row.get('main_artist'))

    # 与游客巡演页一致：把尚未写入 show_series 的多站点批量数据按名称前缀聚合。
    inferred_sql = """
        SELECT SUBSTRING_INDEX(sh.show_name,'·',1) AS series_name,
               SUBSTRING_INDEX(sh.show_name,'·',1) AS main_artist,
               MIN(sh.poster_url) AS poster_url,
               sh.category_id, cat.category_name,
               COUNT(DISTINCT sh.show_id) AS station_count,
               COUNT(DISTINCT sh.city_id) AS city_count,
               MIN(vl.min_price) AS min_price, MAX(vl.max_price) AS max_price,
               MAX(sh.create_time) AS create_time,
               CASE
                 WHEN MAX(CASE WHEN vl.show_status=2 THEN 1 ELSE 0 END)>0 THEN 2
                 WHEN MAX(CASE WHEN vl.show_status=1 THEN 1 ELSE 0 END)>0 THEN 1
                 WHEN MAX(CASE WHEN vl.show_status=3 THEN 1 ELSE 0 END)>0 THEN 3
                 WHEN MAX(CASE WHEN vl.show_status=4 THEN 1 ELSE 0 END)>0 THEN 4
                 ELSE 3
               END AS show_status
        FROM show_item sh JOIN category cat ON cat.category_id=sh.category_id
        LEFT JOIN show_session se ON se.show_id=sh.show_id
        LEFT JOIN v_show_list vl ON vl.show_id=sh.show_id
        WHERE sh.series_id IS NULL AND sh.category_id<>%s AND sh.show_name LIKE '%%·%%'
    """
    inferred_args = [HIDDEN_CATEGORY_ID]
    if keyword:
        inferred_sql += " AND SUBSTRING_INDEX(sh.show_name,'·',1) LIKE %s"
        inferred_args.append('%%%s%%' % keyword)
    if category_id:
        inferred_sql += " AND sh.category_id=%s"; inferred_args.append(int(category_id))
    if city_id:
        inferred_sql += " AND EXISTS (SELECT 1 FROM show_item sx WHERE sx.series_id IS NULL AND sx.city_id=%s AND sx.category_id=sh.category_id AND SUBSTRING_INDEX(sx.show_name,'·',1)=SUBSTRING_INDEX(sh.show_name,'·',1))"
        inferred_args.append(int(city_id))
    inferred_sql += " GROUP BY SUBSTRING_INDEX(sh.show_name,'·',1), sh.category_id, cat.category_name HAVING COUNT(DISTINCT sh.show_id)>1"
    if status:
        inferred_sql += " AND show_status=%s"; inferred_args.append(int(status))
    for row in q(inferred_sql, inferred_args):
        row['series_id'] = None
        row['group_name'] = row['series_name']
        row['inferred'] = True
        row = _s(row)
        row['poster_url'] = resolve_poster(row['series_name'], row.get('category_id'),
                                           row.get('poster_url'), row.get('main_artist'))
        rows.append(row)
    rows.sort(key=lambda row: (row.get('create_time') or '', row.get('series_name') or ''), reverse=True)
    cities = q("SELECT * FROM city ORDER BY city_id")
    categories = q("SELECT * FROM category WHERE category_id<>%s ORDER BY category_id",
                   (HIDDEN_CATEGORY_ID,))
    return ok({'list': rows, 'cities': cities, 'categories': categories})


@admin_bp.route('/admin/series/create', methods=['POST'])
@require_login(role='admin')
def create_series():
    b = request.get_json(silent=True) or request.form
    name = str(b.get('series_name') or '').strip()
    artist = str(b.get('main_artist') or '').strip()
    description = str(b.get('description') or '').strip()
    try:
        category_id = int(b.get('category_id'))
        if not name or len(name) > 100:
            return fail('巡演名称不能为空，且不能超过 100 个字符')
        if category_id == HIDDEN_CATEGORY_ID:
            return fail('该演出类型已停用')
        poster_ok, poster_val = _validate_poster_url(b.get('poster_url'))
        if not poster_ok:
            return fail(poster_val)
        sid = execute("""INSERT INTO show_series(series_name,category_id,main_artist,poster_url,description)
                        VALUES(%s,%s,%s,%s,%s)""",
                      (name, category_id, artist or None, poster_val, description))
        return ok({'series_id': sid}, msg='巡演已创建')
    except pymysql.err.IntegrityError:
        return fail('创建失败：巡演名称已存在')
    except (TypeError, ValueError):
        return fail('巡演类型不正确')
    except Exception as e:
        return fail('创建失败：%s' % e)


@admin_bp.route('/admin/series/<int:series_id>')
@require_login(role='admin')
def admin_series_detail(series_id):
    refresh_sale_statuses()
    series = q("""SELECT ser.*, cat.category_name FROM show_series ser
                 JOIN category cat ON cat.category_id=ser.category_id
                 WHERE ser.series_id=%s AND ser.category_id<>%s""",
               (series_id, HIDDEN_CATEGORY_ID), one=True)
    if not series:
        return fail('巡演不存在')
    stations = q("""
        SELECT sh.show_id, sh.show_name, sh.city_id, c.city_name, sh.category_id,
               COUNT(DISTINCT se.session_id) AS session_count,
               MIN(vl.min_price) AS min_price, MAX(vl.max_price) AS max_price,
               CASE
                 WHEN MAX(CASE WHEN vl.show_status=2 THEN 1 ELSE 0 END)>0 THEN 2
                 WHEN MAX(CASE WHEN vl.show_status=1 THEN 1 ELSE 0 END)>0 THEN 1
                 WHEN MAX(CASE WHEN vl.show_status=3 THEN 1 ELSE 0 END)>0 THEN 3
                 WHEN MAX(CASE WHEN vl.show_status=4 THEN 1 ELSE 0 END)>0 THEN 4
                 ELSE 3
               END AS show_status
        FROM show_item sh JOIN city c ON c.city_id=sh.city_id
        LEFT JOIN show_session se ON se.show_id=sh.show_id
        LEFT JOIN v_show_list vl ON vl.show_id=sh.show_id
        WHERE sh.series_id=%s
        GROUP BY sh.show_id, sh.show_name, sh.city_id, c.city_name, sh.category_id
        ORDER BY c.city_name, sh.show_id
    """, (series_id,))
    out = _s(series)
    out['poster_url'] = resolve_poster(out['series_name'], out.get('category_id'),
                                       out.get('poster_url'), out.get('main_artist'))
    return ok({'series': out, 'stations': [_s(station) for station in stations]})


def _promote_inferred_group(cur, group_name, series_name=None, category_id=None,
                           main_artist=None, poster_url=None, description=None):
    """Persist a legacy name-group as a real series when an admin edits it."""
    cur.execute("""SELECT show_id,show_name,category_id,poster_url,description
                   FROM show_item WHERE series_id IS NULL AND category_id<>%s
                     AND SUBSTRING_INDEX(show_name,'·',1)=%s FOR UPDATE""",
                (HIDDEN_CATEGORY_ID, group_name))
    stations = cur.fetchall()
    if len(stations) < 2:
        return None
    series_name = (series_name or group_name).strip()
    category_id = int(category_id or stations[0]['category_id'])
    main_artist = main_artist or group_name
    poster_url = poster_url if poster_url is not None else stations[0].get('poster_url') or ''
    description = description if description is not None else stations[0].get('description') or ''
    cur.execute("""INSERT INTO show_series(series_name,category_id,main_artist,poster_url,description)
                   VALUES(%s,%s,%s,%s,%s)""",
                (series_name, category_id, main_artist, poster_url, description))
    new_series_id = cur.lastrowid
    for station in stations:
        suffix = station['show_name'][len(group_name):]
        cur.execute("""UPDATE show_item SET series_id=%s,category_id=%s,show_name=%s
                       WHERE show_id=%s AND series_id IS NULL""",
                    (new_series_id, category_id, series_name + suffix, station['show_id']))
    return new_series_id


@admin_bp.route('/admin/series/group')
@require_login(role='admin')
def admin_inferred_series_detail():
    refresh_sale_statuses()
    name = (request.args.get('name') or '').strip()
    if not name:
        return fail('巡演名称不能为空')
    stations = q("""
        SELECT sh.show_id, sh.show_name, sh.city_id, c.city_name, sh.category_id,
               COUNT(DISTINCT se.session_id) AS session_count,
               MIN(vl.min_price) AS min_price, MAX(vl.max_price) AS max_price,
               CASE
                 WHEN MAX(CASE WHEN vl.show_status=2 THEN 1 ELSE 0 END)>0 THEN 2
                 WHEN MAX(CASE WHEN vl.show_status=1 THEN 1 ELSE 0 END)>0 THEN 1
                 WHEN MAX(CASE WHEN vl.show_status=3 THEN 1 ELSE 0 END)>0 THEN 3
                 WHEN MAX(CASE WHEN vl.show_status=4 THEN 1 ELSE 0 END)>0 THEN 4
                 ELSE 3
               END AS show_status
        FROM show_item sh JOIN city c ON c.city_id=sh.city_id
        LEFT JOIN show_session se ON se.show_id=sh.show_id
        LEFT JOIN v_show_list vl ON vl.show_id=sh.show_id
        WHERE sh.series_id IS NULL AND sh.category_id<>%s
          AND SUBSTRING_INDEX(sh.show_name,'·',1)=%s
        GROUP BY sh.show_id, sh.show_name, sh.city_id, c.city_name, sh.category_id
        ORDER BY c.city_name, sh.show_id
    """, (HIDDEN_CATEGORY_ID, name))
    if len(stations) < 2:
        return fail('该巡演已变更或不存在')
    sample = q("""SELECT sh.category_id,cat.category_name,MIN(sh.poster_url) AS poster_url,
                         MIN(sh.description) AS description
                  FROM show_item sh JOIN category cat ON cat.category_id=sh.category_id
                  WHERE sh.series_id IS NULL AND sh.category_id<>%s
                    AND SUBSTRING_INDEX(sh.show_name,'·',1)=%s
                  GROUP BY sh.category_id,cat.category_name LIMIT 1""",
               (HIDDEN_CATEGORY_ID, name), one=True) or {}
    series = {'series_id': None, 'series_name': name, 'main_artist': name,
              'group_name': name, 'inferred': True, **sample}
    series['poster_url'] = resolve_poster(name, series.get('category_id'),
                                           series.get('poster_url'), name)
    return ok({'series': _s(series), 'stations': [_s(station) for station in stations]})


@admin_bp.route('/admin/series/group/update', methods=['POST'])
@require_login(role='admin')
def update_inferred_series():
    b = request.get_json(silent=True) or request.form
    group_name = str(b.get('group_name') or '').strip()
    name = str(b.get('series_name') or '').strip()
    artist = str(b.get('main_artist') or '').strip()
    description = str(b.get('description') or '').strip()
    try:
        category_id = int(b.get('category_id'))
        if not group_name or not name or len(name) > 100 or category_id == HIDDEN_CATEGORY_ID:
            return fail('巡演名称和类型不正确')
        poster_ok, poster_val = _validate_poster_url(b.get('poster_url'))
        if not poster_ok:
            return fail(poster_val)
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                sid = _promote_inferred_group(cur, group_name, name, category_id,
                                              artist, poster_val, description)
                if sid is None:
                    return fail('该巡演已变更或不存在')
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return ok({'series_id': sid}, msg='巡演信息已更新')
    except pymysql.err.IntegrityError:
        return fail('更新失败：巡演名称已存在')
    except (TypeError, ValueError):
        return fail('巡演类型不正确')
    except Exception as e:
        return fail('更新失败：%s' % e)


@admin_bp.route('/admin/series/group/delete', methods=['POST'])
@require_login(role='admin')
def delete_inferred_series():
    b = request.get_json(silent=True) or request.form
    name = str(b.get('group_name') or '').strip()
    if not name:
        return fail('巡演名称不能为空')
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""DELETE FROM show_item WHERE series_id IS NULL AND category_id<>%s
                           AND SUBSTRING_INDEX(show_name,'·',1)=%s""",
                        (HIDDEN_CATEGORY_ID, name))
            if cur.rowcount < 2:
                conn.rollback()
                return fail('该巡演已变更或不存在')
        conn.commit()
        return ok(msg='巡演及其站点已删除')
    except pymysql.err.IntegrityError:
        conn.rollback()
        return fail('删除失败：巡演下已有订单，为保留销售数据不可删除')
    except Exception as e:
        conn.rollback()
        return fail('删除失败：%s' % e)
    finally:
        conn.close()


@admin_bp.route('/admin/series/group/stations/create', methods=['POST'])
@require_login(role='admin')
def create_inferred_station():
    b = request.get_json(silent=True) or request.form
    group_name = str(b.get('group_name') or '').strip()
    show_name = str(b.get('show_name') or '').strip()
    try:
        city_id = int(b.get('city_id'))
        if not group_name or not show_name or len(show_name) > 100:
            return fail('巡演和站点名称不能为空')
        if not q("SELECT city_id FROM city WHERE city_id=%s", (city_id,), one=True):
            return fail('城市不存在')
        poster_ok, poster_val = _validate_poster_url(b.get('poster_url'))
        if not poster_ok:
            return fail(poster_val)
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                series_id = _promote_inferred_group(cur, group_name)
                if series_id is None:
                    return fail('该巡演已变更或不存在')
                cur.execute("SELECT category_id FROM show_series WHERE series_id=%s", (series_id,))
                category_id = cur.fetchone()['category_id']
                cur.execute("""INSERT INTO show_item(show_name,category_id,city_id,series_id,
                               poster_url,description,admin_id) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                            (show_name, category_id, city_id, series_id, poster_val,
                             b.get('description') or '', current_user()['id']))
                show_id = cur.lastrowid
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return ok({'series_id': series_id, 'show_id': show_id}, msg='巡演站点已添加')
    except (TypeError, ValueError):
        return fail('城市信息不正确')
    except Exception as e:
        return fail('添加站点失败：%s' % e)


@admin_bp.route('/admin/series/group/stations/<int:show_id>/delete', methods=['POST'])
@require_login(role='admin')
def delete_inferred_station(show_id):
    b = request.get_json(silent=True) or request.form
    name = str(b.get('group_name') or '').strip()
    if not name:
        return fail('巡演名称不能为空')
    try:
        execute("""DELETE FROM show_item WHERE show_id=%s AND series_id IS NULL
                   AND SUBSTRING_INDEX(show_name,'·',1)=%s""", (show_id, name))
        remaining = q("""SELECT COUNT(*) AS c FROM show_item WHERE series_id IS NULL
                        AND category_id<>%s AND SUBSTRING_INDEX(show_name,'·',1)=%s""",
                      (HIDDEN_CATEGORY_ID, name), one=True)['c']
        return ok({'became_single': remaining == 1}, msg='巡演站点及其场次已删除')
    except pymysql.err.IntegrityError:
        return fail('删除失败：该站点已有订单，为保留销售数据不可删除')


@admin_bp.route('/admin/series/<int:series_id>/update', methods=['POST'])
@require_login(role='admin')
def update_series(series_id):
    b = request.get_json(silent=True) or request.form
    name = str(b.get('series_name') or '').strip()
    artist = str(b.get('main_artist') or '').strip()
    description = str(b.get('description') or '').strip()
    try:
        category_id = int(b.get('category_id'))
        if not name or len(name) > 100:
            return fail('巡演名称不能为空，且不能超过 100 个字符')
        if category_id == HIDDEN_CATEGORY_ID:
            return fail('该演出类型已停用')
        poster_ok, poster_val = _validate_poster_url(b.get('poster_url'))
        if not poster_ok:
            return fail(poster_val)
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT series_id FROM show_series WHERE series_id=%s FOR UPDATE", (series_id,))
                if not cur.fetchone():
                    return fail('巡演不存在')
                cur.execute("""UPDATE show_series SET series_name=%s,category_id=%s,main_artist=%s,
                               poster_url=%s,description=%s WHERE series_id=%s""",
                            (name, category_id, artist or None, poster_val, description, series_id))
                cur.execute("UPDATE show_item SET category_id=%s WHERE series_id=%s",
                            (category_id, series_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return ok(msg='巡演信息已更新')
    except pymysql.err.IntegrityError:
        return fail('更新失败：巡演名称已存在')
    except (TypeError, ValueError):
        return fail('巡演类型不正确')
    except Exception as e:
        return fail('更新失败：%s' % e)


@admin_bp.route('/admin/series/<int:series_id>/delete', methods=['POST'])
@require_login(role='admin')
def delete_series(series_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT series_id FROM show_series WHERE series_id=%s FOR UPDATE", (series_id,))
            if not cur.fetchone():
                return fail('巡演不存在')
            # 删除巡演时一并移除站点及其场次、票档；已有订单的站点受外键保护。
            cur.execute("DELETE FROM show_item WHERE series_id=%s", (series_id,))
            cur.execute("DELETE FROM show_series WHERE series_id=%s", (series_id,))
        conn.commit()
        return ok(msg='巡演及其站点已删除')
    except pymysql.err.IntegrityError:
        conn.rollback()
        return fail('删除失败：巡演下已有订单，为保留销售数据不可删除')
    except Exception as e:
        conn.rollback()
        return fail('删除失败：%s' % e)
    finally:
        conn.close()


@admin_bp.route('/admin/series/<int:series_id>/stations/create', methods=['POST'])
@require_login(role='admin')
def create_series_station(series_id):
    b = request.get_json(silent=True) or request.form
    name = str(b.get('show_name') or '').strip()
    try:
        city_id = int(b.get('city_id'))
        series = q("SELECT series_name,category_id FROM show_series WHERE series_id=%s", (series_id,), one=True)
        if not series:
            return fail('巡演不存在')
        if not name or len(name) > 100:
            return fail('站点名称不能为空，且不能超过 100 个字符')
        if not q("SELECT city_id FROM city WHERE city_id=%s", (city_id,), one=True):
            return fail('城市不存在')
        poster_ok, poster_val = _validate_poster_url(b.get('poster_url'))
        if not poster_ok:
            return fail(poster_val)
        show_id = execute("""INSERT INTO show_item(show_name,category_id,city_id,series_id,
                           poster_url,description,admin_id) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                          (name, series['category_id'], city_id, series_id,
                           poster_val, b.get('description') or '', current_user()['id']))
        return ok({'show_id': show_id}, msg='巡演站点已添加')
    except (TypeError, ValueError):
        return fail('城市信息不正确')
    except Exception as e:
        return fail('添加站点失败：%s' % e)


@admin_bp.route('/admin/series/<int:series_id>/stations/<int:show_id>/delete', methods=['POST'])
@require_login(role='admin')
def delete_series_station(series_id, show_id):
    try:
        station = q("SELECT show_id FROM show_item WHERE show_id=%s AND series_id=%s",
                    (show_id, series_id), one=True)
        if not station:
            return fail('巡演站点不存在')
        execute("DELETE FROM show_item WHERE show_id=%s AND series_id=%s", (show_id, series_id))
        return ok(msg='巡演站点及其场次已删除')
    except pymysql.err.IntegrityError:
        return fail('删除失败：该站点已有订单，为保留销售数据不可删除')


@admin_bp.route('/admin/uploads/poster', methods=['POST'])
@require_login(role='admin')
def upload_poster():
    """上传演出海报，返回可直接写入 show_item.poster_url 的地址。"""
    image = request.files.get('poster')
    if not image or not image.filename:
        return fail('请选择海报图片')

    ext = os.path.splitext(secure_filename(image.filename))[1].lower()
    if ext not in _POSTER_EXTENSIONS or image.mimetype not in _POSTER_MIMETYPES:
        return fail('仅支持 JPG、PNG、GIF、WEBP 图片')
    if not _has_image_signature(image, ext):
        return fail('文件内容不是有效的图片')
    if request.content_length and request.content_length > current_app.config.get('MAX_CONTENT_LENGTH', 5 * 1024 * 1024):
        return fail('图片大小不能超过 5MB')

    upload_dir = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    filename = f'{uuid.uuid4().hex}{ext}'
    image.save(os.path.join(upload_dir, filename))
    return ok({'url': f'/static/img/uploads/{filename}'}, msg='海报上传成功')


@admin_bp.route('/admin/session/create', methods=['POST'])
@require_login(role='admin')
def create_session():
    b = request.get_json(silent=True) or request.form
    try:
        show_id = int(b.get('show_id'))
        venue_id = int(b.get('venue_id'))
        parsed_show_time = _parse_show_time(b.get('show_time'))
        if not parsed_show_time:
            return fail('场次添加失败：开演时间格式不正确')
        now = datetime.now()
        if parsed_show_time <= now:
            return fail('场次添加失败：开演时间必须晚于当前时间')
        sale_start = _sale_start_for(parsed_show_time, now)
        sale_status = _sale_status_for(parsed_show_time, sale_start, [], now)
        show = q("SELECT city_id FROM show_item WHERE show_id=%s", (show_id,), one=True)
        venue = q("SELECT city_id FROM venue WHERE venue_id=%s", (venue_id,), one=True)
        if not show:
            return fail('场次添加失败：演出不存在')
        if not venue:
            return fail('场次添加失败：场馆不存在')
        if show['city_id'] != venue['city_id']:
            return fail('场次添加失败：场馆必须属于演出所在城市')
        sid = execute("""INSERT INTO show_session(show_id,venue_id,show_time,sale_start,sale_status)
                         VALUES(%s,%s,%s,%s,%s)""",
                      (show_id, venue_id, parsed_show_time, sale_start, sale_status))
        return ok({'session_id': sid}, msg='场次已添加')
    except (TypeError, ValueError):
        return fail('场次添加失败：场次或场馆信息不正确')
    except pymysql.err.IntegrityError:
        return fail('场次添加失败：该演出已存在相同开演时间')
    except Exception as e:
        return fail('场次添加失败：%s' % e)


@admin_bp.route('/admin/session/<int:session_id>/update', methods=['POST'])
@require_login(role='admin')
def update_session(session_id):
    b = request.get_json(silent=True) or request.form
    conn = get_conn()
    try:
        show_id = int(b.get('show_id'))
        venue_id = int(b.get('venue_id'))
        show_time = _parse_show_time(b.get('show_time'))
        if not show_time:
            return fail('修改失败：开演时间格式不正确')
        now = datetime.now()
        if show_time <= now:
            return fail('修改失败：开演时间必须晚于当前时间')

        submitted_tiers = b.get('tiers') or []
        new_tiers = b.get('new_tiers') or []
        delete_tier_ids = b.get('delete_tier_ids') or []
        if (not isinstance(submitted_tiers, list) or not isinstance(new_tiers, list)
                or not isinstance(delete_tier_ids, list)):
            return fail('修改失败：票档数据格式不正确')

        with conn.cursor() as cur:
            cur.execute("""SELECT se.session_id, se.show_id, se.venue_id, se.show_time, se.sale_start,
                                  (SELECT COUNT(*) FROM ticket_order o WHERE o.session_id=se.session_id) AS order_count
                           FROM show_session se
                           WHERE se.session_id=%s FOR UPDATE""", (session_id,))
            session = cur.fetchone()
            if not session:
                return fail('修改失败：场次不存在')
            if session['show_id'] != show_id:
                return fail('修改失败：场次不属于当前演出')
            if int(session['order_count'] or 0) > 0:
                if int(session['venue_id']) != venue_id or session['show_time'] != show_time:
                    return fail('修改失败：该场次已有售出订单，为保障观演权益不可修改场馆与开演时间')

            cur.execute("SELECT city_id FROM show_item WHERE show_id=%s", (show_id,))
            show = cur.fetchone()
            if not show:
                return fail('修改失败：演出不存在')
            cur.execute("SELECT city_id,capacity FROM venue WHERE venue_id=%s FOR UPDATE", (venue_id,))
            venue = cur.fetchone()
            if not venue:
                return fail('修改失败：场馆不存在')
            if venue['city_id'] != show['city_id']:
                return fail('修改失败：场馆必须属于演出所在城市')

            cur.execute("""SELECT tier_id,tier_name,price,total_seats,sold_seats
                           FROM ticket_tier WHERE session_id=%s FOR UPDATE""", (session_id,))
            current_tiers = cur.fetchall()
            current_by_id = {int(t['tier_id']): t for t in current_tiers}
            try:
                delete_tier_ids = [int(tier_id) for tier_id in delete_tier_ids]
            except (TypeError, ValueError):
                return fail('修改失败：待删除票档编号不正确')
            if len(set(delete_tier_ids)) != len(delete_tier_ids):
                return fail('修改失败：待删除票档重复')
            for tier_id in delete_tier_ids:
                tier = current_by_id.get(tier_id)
                if not tier:
                    return fail('修改失败：待删除票档不存在')
                if int(tier['sold_seats']) > 0:
                    return fail(f'修改失败：票档【{tier["tier_name"]}】已有售出订单，不可删除')
            changed_ids = set()
            final_tiers = {int(t['tier_id']): {
                'tier_id': int(t['tier_id']), 'tier_name': t['tier_name'],
                'price': Decimal(str(t['price'])), 'total_seats': int(t['total_seats']),
                'sold_seats': int(t['sold_seats'])
            } for t in current_tiers}
            for tier_id in delete_tier_ids:
                final_tiers.pop(tier_id, None)

            for item in submitted_tiers:
                if not isinstance(item, dict):
                    return fail('修改失败：票档数据格式不正确')
                try:
                    tier_id = int(item.get('tier_id'))
                except (TypeError, ValueError):
                    return fail('修改失败：票档编号不正确')
                if tier_id not in current_by_id or tier_id in changed_ids or tier_id in delete_tier_ids:
                    return fail('修改失败：票档不存在或重复')
                changed_ids.add(tier_id)
                name = str(item.get('tier_name') or '').strip()
                price = _parse_positive_price(item.get('price'))
                seats = _parse_positive_seats(item.get('total_seats'))
                if not name or len(name) > 50 or price is None or seats is None:
                    return fail('修改失败：票档名称不能为空，票价和总票数必须大于 0')
                old = current_by_id[tier_id]
                old_price = Decimal(str(old['price'])).quantize(Decimal('0.01'))
                if int(old['sold_seats']) > 0 and name != old['tier_name']:
                    return fail(f'修改失败：票档【{old["tier_name"]}】已有售出订单，不可修改名称')
                if seats < int(old['sold_seats']):
                    return fail(f'修改失败：票档【{old["tier_name"]}】总票数({seats}张)不能小于已售数量({old["sold_seats"]}张)')
                final_tiers[tier_id] = {
                    'tier_id': tier_id, 'tier_name': name, 'price': price,
                    'total_seats': seats, 'sold_seats': int(old['sold_seats'])
                }

            prepared_new = []
            for item in new_tiers:
                if not isinstance(item, dict):
                    return fail('修改失败：新增票档数据格式不正确')
                name = str(item.get('tier_name') or '').strip()
                price = _parse_positive_price(item.get('price'))
                seats = _parse_positive_seats(item.get('total_seats'))
                if not name or len(name) > 50 or price is None or seats is None:
                    return fail('修改失败：票档名称不能为空，票价和总票数必须大于 0')
                prepared_new.append({'tier_name': name, 'price': price,
                                     'total_seats': seats, 'sold_seats': 0})

            allocated = sum(t['total_seats'] for t in final_tiers.values()) + sum(
                t['total_seats'] for t in prepared_new)
            if allocated > int(venue['capacity']):
                return fail(f'修改失败：票档总票数({allocated}张)超过场馆容量({venue["capacity"]}座)')

            for tier_id in delete_tier_ids:
                cur.execute("DELETE FROM ticket_tier WHERE tier_id=%s AND session_id=%s AND sold_seats=0",
                            (tier_id, session_id))
                if cur.rowcount != 1:
                    return fail('已售票档不能删除')

            for tier_id, tier in final_tiers.items():
                if tier_id in changed_ids:
                    cur.execute("""UPDATE ticket_tier SET tier_name=%s,price=%s,total_seats=%s
                                   WHERE tier_id=%s AND session_id=%s""",
                                (tier['tier_name'], tier['price'], tier['total_seats'], tier_id, session_id))
            for tier in prepared_new:
                cur.execute("""INSERT INTO ticket_tier(session_id,tier_name,price,total_seats,sold_seats)
                               VALUES(%s,%s,%s,%s,0)""",
                            (session_id, tier['tier_name'], tier['price'], tier['total_seats']))

            if session.get('sale_start') and show_time == session['show_time']:
                sale_start = session['sale_start']
            else:
                sale_start = _sale_start_for(show_time, now)
            all_tiers = list(final_tiers.values()) + prepared_new
            sale_status = _sale_status_for(show_time, sale_start, all_tiers, now)
            cur.execute("""UPDATE show_session SET venue_id=%s,show_time=%s,
                           sale_start=%s,sale_status=%s WHERE session_id=%s""",
                        (venue_id, show_time, sale_start, sale_status, session_id))
        conn.commit()
        return ok(msg='场次已更新')
    except pymysql.err.IntegrityError as e:
        conn.rollback()
        if getattr(e, 'args', [None])[0] == 1062:
            return fail('修改失败：开演时间或票档名称重复')
        return fail('修改失败：数据违反约束')
    except (TypeError, ValueError):
        conn.rollback()
        return fail('修改失败：场次信息格式不正确')
    except Exception as e:
        conn.rollback()
        return fail('修改失败：%s' % e)
    finally:
        conn.close()


@admin_bp.route('/admin/session/<int:session_id>/delete', methods=['POST'])
@require_login(role='admin')
def delete_session(session_id):
    b = request.get_json(silent=True) or request.form
    try:
        supplied_show_id = b.get('show_id')
        show_id = int(supplied_show_id) if supplied_show_id not in (None, '') else None
        session = q("SELECT show_id FROM show_session WHERE session_id=%s", (session_id,), one=True)
        if not session:
            return fail('删除失败：场次不存在')
        if show_id is not None and session['show_id'] != show_id:
            return fail('删除失败：场次不属于当前演出')
        execute("DELETE FROM show_session WHERE session_id=%s", (session_id,))
        return ok(msg='场次及其票档已删除')
    except pymysql.err.IntegrityError:
        return fail('删除失败：该场次已有订单，为保留销售数据不可删除')


@admin_bp.route('/admin/tier/create', methods=['POST'])
@require_login(role='admin')
def create_tier():
    b = request.get_json(silent=True) or request.form
    conn = get_conn()
    try:
        session_id = int(b.get('session_id'))
        supplied_show_id = b.get('show_id')
        tier_name = str(b.get('tier_name') or '').strip()
        price = _parse_positive_price(b.get('price'))
        seats = _parse_positive_seats(b.get('total_seats'))
        if not tier_name or len(tier_name) > 50 or price is None or seats is None:
            return fail('票档添加失败：名称不能为空，票价和总票数必须大于 0')
        with conn.cursor() as cur:
            cur.execute("""SELECT se.show_id,se.show_time,se.sale_start,v.capacity
                           FROM show_session se JOIN venue v ON v.venue_id=se.venue_id
                           WHERE se.session_id=%s FOR UPDATE""", (session_id,))
            session = cur.fetchone()
            if not session:
                return fail('票档添加失败：场次不存在')
            if supplied_show_id is not None and int(supplied_show_id) != session['show_id']:
                return fail('票档添加失败：场次不属于当前演出')
            cur.execute("SELECT COALESCE(SUM(total_seats),0) AS allocated FROM ticket_tier WHERE session_id=%s",
                        (session_id,))
            allocated = int(cur.fetchone()['allocated'])
            if allocated + seats > int(session['capacity']):
                return fail(f'票档添加失败：票档总票数({allocated + seats}张)超过场馆容量({session["capacity"]}座)')
            cur.execute("""INSERT INTO ticket_tier(session_id,tier_name,price,total_seats,sold_seats)
                           VALUES(%s,%s,%s,%s,0)""",
                        (session_id, tier_name, price, seats))
            tid = cur.lastrowid
            cur.execute("SELECT tier_name,total_seats,sold_seats FROM ticket_tier WHERE session_id=%s",
                        (session_id,))
            tiers = cur.fetchall()
            now = datetime.now()
            status = _sale_status_for(session['show_time'], session['sale_start'], tiers, now)
            cur.execute("UPDATE show_session SET sale_status=%s WHERE session_id=%s",
                        (status, session_id))
        conn.commit()
        return ok({'tier_id': tid}, msg='票档已添加')
    except (TypeError, ValueError):
        conn.rollback()
        return fail('票档添加失败：票档数据格式不正确')
    except pymysql.err.IntegrityError:
        conn.rollback()
        return fail('票档添加失败：同一场次已存在同名票档')
    except Exception as e:
        conn.rollback()
        return fail('票档添加失败：%s' % e)
    finally:
        conn.close()


@admin_bp.route('/admin/tier/<int:tier_id>/delete', methods=['POST'])
@require_login(role='admin')
def delete_tier(tier_id):
    b = request.get_json(silent=True) or request.form
    try:
        supplied_show_id = b.get('show_id')
        show_id = int(supplied_show_id) if supplied_show_id not in (None, '') else None
        tier = q("""SELECT t.tier_id, se.show_id
                   FROM ticket_tier t JOIN show_session se ON se.session_id=t.session_id
                   WHERE t.tier_id=%s""", (tier_id,), one=True)
        if not tier:
            return fail('删除失败：票档不存在')
        if show_id is not None and tier['show_id'] != show_id:
            return fail('删除失败：票档不属于当前演出')
        execute("DELETE FROM ticket_tier WHERE tier_id=%s", (tier_id,))
        return ok(msg='票档已删除')
    except pymysql.err.IntegrityError:
        return fail('删除失败：该票档已有订单，为保留销售数据不可删除')
