# -*- coding: utf-8 -*-
"""管理员接口：演出/场次/票档的查询与增删改。"""
import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

import pymysql
from flask import Blueprint, current_app, request
from werkzeug.utils import secure_filename

from db import q, execute, get_conn
from posters import resolve_poster
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
        return price.quantize(Decimal('0.01'))
    except InvalidOperation:
        return None


def _parse_positive_seats(value):
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
    where = ' WHERE category_id<>%s'
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
        if hasattr(v, 'isoformat'):
            out[k] = v.isoformat(sep=' ')
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
        sid = execute("""INSERT INTO show_item(show_name,category_id,city_id,poster_url,description,admin_id)
                         VALUES(%s,%s,%s,%s,%s,%s)""",
                      (b.get('show_name'), category_id, int(b.get('city_id')),
                       b.get('poster_url') or '', b.get('description') or '', current_user()['id']))
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
        target_city = int(b.get('city_id'))
        show = q("SELECT city_id FROM show_item WHERE show_id=%s", (show_id,), one=True)
        if not show:
            return fail('演出不存在')
        if show['city_id'] != target_city:
            session_count = q("SELECT COUNT(*) AS c FROM show_session WHERE show_id=%s",
                              (show_id,), one=True)['c']
            if session_count:
                return fail('该演出已有场次，不能直接更换城市；请先处理场次')
        execute("""UPDATE show_item SET show_name=%s,category_id=%s,city_id=%s,poster_url=%s,description=%s
                   WHERE show_id=%s""",
                (b.get('show_name'), category_id, target_city,
                 b.get('poster_url') or '', b.get('description') or '', show_id))
        return ok(msg='演出信息已更新')
    except (TypeError, ValueError):
        return fail('演出信息格式不正确')
    except Exception as e:
        return fail('更新失败：%s' % e)


@admin_bp.route('/admin/shows/<int:show_id>/delete', methods=['POST'])
@require_login(role='admin')
def delete_show(show_id):
    try:
        execute("DELETE FROM show_item WHERE show_id=%s", (show_id,))
        return ok(msg='演出及其场次、票档、图片已级联删除')
    except pymysql.err.IntegrityError:
        return fail('删除失败：该演出已有订单，为保留销售数据不可删除')


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
            cur.execute("""SELECT show_id FROM show_session
                           WHERE session_id=%s FOR UPDATE""", (session_id,))
            session = cur.fetchone()
            if not session:
                return fail('修改失败：场次不存在')
            if session['show_id'] != show_id:
                return fail('修改失败：场次不属于当前演出')

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
                    return fail('已售票档不能删除')
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
                if int(old['sold_seats']) > 0 and (
                        name != old['tier_name'] or price != old_price or seats != int(old['total_seats'])):
                    return fail('该票档已售不为 0，无法修改')
                if seats < int(old['sold_seats']):
                    return fail('修改失败：总票数不能小于已售数量')
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
                return fail('票档总票数超过场馆容量')

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
                return fail('票档总票数超过场馆容量')
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
