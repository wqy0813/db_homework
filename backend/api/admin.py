# -*- coding: utf-8 -*-
"""管理员接口：演出/场次/票档的查询与增删改。"""
import os
import uuid
from datetime import datetime, timedelta

import pymysql
from flask import Blueprint, current_app, request
from werkzeug.utils import secure_filename

from db import q, execute
from .helpers import ok, fail, require_login, current_user

admin_bp = Blueprint('api_admin', __name__)

_POSTER_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
_POSTER_MIMETYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}


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
    rows = q("SELECT * FROM v_show_list ORDER BY show_id DESC")
    cities = q("SELECT * FROM city ORDER BY city_id")
    cats = q("SELECT * FROM category ORDER BY category_id")
    return ok({'list': [_s(r) for r in rows], 'cities': cities, 'categories': cats})


def _s(r):
    out = dict(r)
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
        sid = execute("""INSERT INTO show_item(show_name,category_id,city_id,poster_url,description,admin_id)
                         VALUES(%s,%s,%s,%s,%s,%s)""",
                      (b.get('show_name'), int(b.get('category_id')), int(b.get('city_id')),
                       b.get('poster_url') or '', b.get('description') or '', current_user()['id']))
        return ok({'show_id': sid}, msg='演出已创建')
    except Exception as e:
        return fail('创建失败：%s' % e)


@admin_bp.route('/admin/shows/<int:show_id>')
@require_login(role='admin')
def show_detail(show_id):
    show = q("""SELECT s.*, c.city_name, cat.category_name
                FROM show_item s
                JOIN city c ON c.city_id=s.city_id
                JOIN category cat ON cat.category_id=s.category_id
                WHERE s.show_id=%s""", (show_id,), one=True)
    if not show:
        return fail('演出不存在')
    sessions = q("""SELECT se.session_id, se.show_id, se.venue_id,
                           se.show_time, se.sale_start,
                           se.sale_status,
                           v.venue_name
                    FROM show_session se
                    JOIN venue v ON v.venue_id=se.venue_id
                    WHERE se.show_id=%s ORDER BY se.show_time""", (show_id,))
    tiers = q("""SELECT t.*, t.total_seats-t.sold_seats AS remain FROM ticket_tier t
                 WHERE t.session_id IN (SELECT session_id FROM show_session WHERE show_id=%s)
                 ORDER BY t.session_id, t.price DESC""", (show_id,))
    images = q("SELECT * FROM show_image WHERE show_id=%s ORDER BY sort_no,image_id", (show_id,))
    venues = q("SELECT * FROM venue WHERE city_id=%s ORDER BY venue_id", (show['city_id'],))
    tbs = {}
    for t in tiers:
        t['price'] = float(t['price'])
        tbs.setdefault(t['session_id'], []).append(t)
    return ok({'show': _s(show), 'images': [_s(x) for x in images],
               'sessions': [_s(x) for x in sessions],
               'tiers': tbs, 'venues': [_s(x) for x in venues]})


@admin_bp.route('/admin/shows/<int:show_id>/update', methods=['POST'])
@require_login(role='admin')
def update_show(show_id):
    b = request.get_json(silent=True) or request.form
    try:
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
                (b.get('show_name'), int(b.get('category_id')), target_city,
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


@admin_bp.route('/admin/shows/<int:show_id>/images/add', methods=['POST'])
@require_login(role='admin')
def add_show_image(show_id):
    b = request.get_json(silent=True) or request.form
    image_url = (b.get('image_url') or '').strip()
    try:
        sort_no = int(b.get('sort_no') or 0)
    except (TypeError, ValueError):
        return fail('图片顺序必须是整数')
    if not q("SELECT 1 FROM show_item WHERE show_id=%s", (show_id,), one=True):
        return fail('演出不存在')
    if not image_url or len(image_url) > 255:
        return fail('图片地址不能为空且不能超过 255 个字符')
    if sort_no < 0 or sort_no > 127:
        return fail('图片顺序必须在 0-127 之间')
    try:
        iid = execute("INSERT INTO show_image(show_id,image_url,sort_no) VALUES(%s,%s,%s)",
                      (show_id, image_url, sort_no))
        return ok({'image_id': iid}, msg='图片已添加')
    except Exception as e:
        return fail('图片添加失败：%s' % e)


@admin_bp.route('/admin/shows/<int:show_id>/images/<int:image_id>/delete', methods=['POST'])
@require_login(role='admin')
def delete_show_image(show_id, image_id):
    try:
        if not q("SELECT 1 FROM show_image WHERE image_id=%s AND show_id=%s", (image_id, show_id), one=True):
            return fail('图片不存在或不属于当前演出')
        execute("DELETE FROM show_image WHERE image_id=%s AND show_id=%s", (image_id, show_id))
        return ok(msg='图片已删除')
    except Exception as e:
        return fail('图片删除失败：%s' % e)


@admin_bp.route('/admin/session/create', methods=['POST'])
@require_login(role='admin')
def create_session():
    b = request.get_json(silent=True) or request.form
    show_id = int(b.get('show_id'))
    show_time = (b.get('show_time') or '').replace('T', ' ')
    try:
        try:
            parsed_show_time = datetime.strptime(show_time, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            parsed_show_time = datetime.strptime(show_time, '%Y-%m-%d %H:%M')
        sale_start = parsed_show_time - timedelta(days=30)
        show = q("SELECT city_id FROM show_item WHERE show_id=%s", (show_id,), one=True)
        venue = q("SELECT city_id FROM venue WHERE venue_id=%s", (int(b.get('venue_id')),), one=True)
        if not show:
            return fail('场次添加失败：演出不存在')
        if not venue:
            return fail('场次添加失败：场馆不存在')
        if show['city_id'] != venue['city_id']:
            return fail('场次添加失败：场馆必须属于演出所在城市')
        sid = execute("""INSERT INTO show_session(show_id,venue_id,show_time,sale_start,sale_status)
                         VALUES(%s,%s,%s,%s,1)""",
                      (show_id, int(b.get('venue_id')), show_time, sale_start))
        return ok({'session_id': sid}, msg='场次已添加')
    except pymysql.err.IntegrityError:
        return fail('场次添加失败：该演出已存在相同开演时间')
    except Exception as e:
        return fail('场次添加失败：%s' % e)


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
    try:
        session_id = int(b.get('session_id'))
        session = q("SELECT show_id FROM show_session WHERE session_id=%s", (session_id,), one=True)
        if not session:
            return fail('票档添加失败：场次不存在')
        supplied_show_id = b.get('show_id')
        if supplied_show_id is not None and int(supplied_show_id) != session['show_id']:
            return fail('票档添加失败：场次不属于当前演出')
        tid = execute("""INSERT INTO ticket_tier(session_id,tier_name,price,total_seats,sold_seats)
                         VALUES(%s,%s,%s,%s,0)""",
                      (session_id, b.get('tier_name'),
                       float(b.get('price')), int(b.get('total_seats'))))
        return ok({'tier_id': tid}, msg='票档已添加')
    except pymysql.err.IntegrityError:
        return fail('票档添加失败：同一场次已存在同名票档')
    except Exception as e:
        return fail('票档添加失败：%s' % e)


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
