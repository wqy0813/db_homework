# -*- coding: utf-8 -*-
"""个人资料接口：收货地址、常用购票人的查询与维护。"""
import re

import pymysql
from flask import Blueprint, request

from db import q, execute, get_conn
from .helpers import ok, fail, require_login, current_user

profile_bp = Blueprint('api_profile', __name__)

PHONE_RE = re.compile(r'^1\d{10}$')
ID_CARD_RE = re.compile(r'^\d{17}[\dXx]$')


def _body():
    return request.get_json(silent=True) or request.form


def _address_values(body):
    receiver = (body.get('receiver_name') or '').strip()
    phone = (body.get('phone') or '').strip()
    detail = (body.get('address_detail') or '').strip()
    if not receiver or len(receiver) > 50:
        raise ValueError('收货人姓名不能为空且不能超过 50 个字符')
    if not PHONE_RE.fullmatch(phone):
        raise ValueError('手机号格式不正确')
    if not detail or len(detail) > 200:
        raise ValueError('收货地址不能为空且不能超过 200 个字符')
    is_default = 1 if str(body.get('is_default') or '0').lower() in ('1', 'true', 'yes', 'on') else 0
    return receiver, phone, detail, is_default


@profile_bp.route('/addresses')
@require_login(role='user')
def list_addresses():
    uid = current_user()['id']
    rows = q("SELECT * FROM shipping_address WHERE user_id=%s ORDER BY is_default DESC,address_id", (uid,))
    return ok({'list': rows})


@profile_bp.route('/addresses/add', methods=['POST'])
@require_login(role='user')
def add_address():
    uid = current_user()['id']
    try:
        receiver, phone, detail, is_default = _address_values(_body())
    except ValueError as e:
        return fail(str(e))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            conn.begin()
            cur.execute("SELECT COUNT(*) AS c FROM shipping_address WHERE user_id=%s", (uid,))
            first = cur.fetchone()['c'] == 0
            if is_default or first:
                cur.execute("UPDATE shipping_address SET is_default=0 WHERE user_id=%s", (uid,))
                is_default = 1
            cur.execute("""INSERT INTO shipping_address(user_id,receiver_name,phone,address_detail,is_default)
                           VALUES(%s,%s,%s,%s,%s)""",
                        (uid, receiver, phone, detail, is_default))
            aid = cur.lastrowid
        conn.commit()
        return ok({'address_id': aid}, msg='收货信息已添加')
    except Exception as e:
        conn.rollback()
        return fail('添加收货信息失败：%s' % e)
    finally:
        conn.close()


@profile_bp.route('/addresses/update', methods=['POST'])
@require_login(role='user')
def update_address():
    uid = current_user()['id']
    body = _body()
    try:
        aid = int(body.get('address_id'))
        receiver, phone, detail, is_default = _address_values(body)
    except (TypeError, ValueError) as e:
        return fail(str(e) if isinstance(e, ValueError) else '地址编号不正确')
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            conn.begin()
            cur.execute("SELECT is_default FROM shipping_address WHERE address_id=%s AND user_id=%s FOR UPDATE",
                        (aid, uid))
            old = cur.fetchone()
            if not old:
                conn.rollback()
                return fail('收货信息不存在或无权操作')
            cur.execute("SELECT 1 FROM ticket_order WHERE address_id=%s LIMIT 1", (aid,))
            if cur.fetchone():
                conn.rollback()
                return fail('该收货信息已用于订单，不能修改历史订单地址')
            if is_default:
                cur.execute("UPDATE shipping_address SET is_default=0 WHERE user_id=%s", (uid,))
            replacement = None
            if not is_default and old['is_default']:
                cur.execute("""SELECT address_id FROM shipping_address
                               WHERE user_id=%s AND address_id<>%s
                               ORDER BY address_id LIMIT 1""", (uid, aid))
                candidate = cur.fetchone()
                if candidate:
                    replacement = candidate['address_id']
                else:
                    # 用户只有这一条地址时，不能让账户进入“无默认地址”状态。
                    is_default = 1
            cur.execute("""UPDATE shipping_address
                           SET receiver_name=%s, phone=%s, address_detail=%s, is_default=%s
                           WHERE address_id=%s AND user_id=%s""",
                        (receiver, phone, detail, is_default, aid, uid))
            if replacement is not None:
                cur.execute("UPDATE shipping_address SET is_default=1 WHERE address_id=%s", (replacement,))
        conn.commit()
        return ok(msg='收货信息已更新')
    except Exception as e:
        conn.rollback()
        return fail('更新收货信息失败：%s' % e)
    finally:
        conn.close()


@profile_bp.route('/addresses/default', methods=['POST'])
@require_login(role='user')
def set_default_address():
    uid = current_user()['id']
    try:
        aid = int(_body().get('address_id'))
    except (TypeError, ValueError):
        return fail('地址编号不正确')
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            conn.begin()
            cur.execute("SELECT 1 FROM shipping_address WHERE address_id=%s AND user_id=%s FOR UPDATE", (aid, uid))
            if not cur.fetchone():
                conn.rollback()
                return fail('收货信息不存在或无权操作')
            cur.execute("UPDATE shipping_address SET is_default=0 WHERE user_id=%s", (uid,))
            cur.execute("UPDATE shipping_address SET is_default=1 WHERE address_id=%s AND user_id=%s", (aid, uid))
        conn.commit()
        return ok(msg='默认收货信息已设置')
    except Exception as e:
        conn.rollback()
        return fail('设置默认收货信息失败：%s' % e)
    finally:
        conn.close()


@profile_bp.route('/addresses/delete', methods=['POST'])
@require_login(role='user')
def delete_address():
    uid = current_user()['id']
    try:
        aid = int(_body().get('address_id'))
    except (TypeError, ValueError):
        return fail('地址编号不正确')
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            conn.begin()
            cur.execute("SELECT is_default FROM shipping_address WHERE address_id=%s AND user_id=%s FOR UPDATE",
                        (aid, uid))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return fail('收货信息不存在或无权操作')
            cur.execute("DELETE FROM shipping_address WHERE address_id=%s AND user_id=%s", (aid, uid))
            if row['is_default']:
                cur.execute("""UPDATE shipping_address SET is_default=1
                               WHERE user_id=%s ORDER BY address_id LIMIT 1""", (uid,))
        conn.commit()
        return ok(msg='收货信息已删除')
    except pymysql.err.IntegrityError:
        conn.rollback()
        return fail('删除失败：该收货信息已被订单引用，为保留历史订单不可删除')
    except Exception as e:
        conn.rollback()
        return fail('删除收货信息失败：%s' % e)
    finally:
        conn.close()


def _attendee_values(body):
    name = (body.get('attendee_name') or '').strip()
    id_no = (body.get('id_no') or '').strip()
    try:
        id_type = int(body.get('id_type'))
    except (TypeError, ValueError):
        raise ValueError('证件类型不正确')
    if not name or len(name) > 50:
        raise ValueError('购票人姓名不能为空且不能超过 50 个字符')
    if id_type not in (1, 2, 3, 4, 5):
        raise ValueError('证件类型不正确')
    if id_type == 1 and not ID_CARD_RE.fullmatch(id_no):
        raise ValueError('身份证号应为 18 位，末位可为 X')
    if id_type != 1 and not 5 <= len(id_no) <= 30:
        raise ValueError('证件号长度应为 5-30 个字符')
    return name, id_type, id_no


@profile_bp.route('/attendees')
@require_login(role='user')
def list_attendees():
    uid = current_user()['id']
    rows = q("SELECT * FROM attendee WHERE user_id=%s ORDER BY attendee_id", (uid,))
    return ok({'list': rows})


@profile_bp.route('/attendees/add', methods=['POST'])
@require_login(role='user')
def add_attendee():
    uid = current_user()['id']
    try:
        name, id_type, id_no = _attendee_values(_body())
        aid = execute("""INSERT INTO attendee(user_id,attendee_name,id_type,id_no)
                         VALUES(%s,%s,%s,%s)""", (uid, name, id_type, id_no))
        return ok({'attendee_id': aid}, msg='购票人已添加')
    except ValueError as e:
        return fail(str(e))
    except pymysql.err.IntegrityError:
        return fail('添加失败：该证件类型+证件号已存在（同一用户不可重复）')


@profile_bp.route('/attendees/update', methods=['POST'])
@require_login(role='user')
def update_attendee():
    uid = current_user()['id']
    body = _body()
    try:
        aid = int(body.get('attendee_id'))
        name, id_type, id_no = _attendee_values(body)
    except (TypeError, ValueError) as e:
        return fail(str(e) if isinstance(e, ValueError) else '购票人编号不正确')
    try:
        if not q("SELECT 1 FROM attendee WHERE attendee_id=%s AND user_id=%s", (aid, uid), one=True):
            return fail('购票人不存在或无权操作')
        if q("SELECT 1 FROM order_item WHERE attendee_id=%s LIMIT 1", (aid,), one=True):
            return fail('该购票人已用于订单，不能修改历史订单购票人信息')
        execute("""UPDATE attendee SET attendee_name=%s,id_type=%s,id_no=%s
                   WHERE attendee_id=%s AND user_id=%s""", (name, id_type, id_no, aid, uid))
        return ok(msg='购票人已更新')
    except pymysql.err.IntegrityError:
        return fail('更新失败：该证件类型+证件号已存在，或购票人已被订单引用')


@profile_bp.route('/attendees/delete', methods=['POST'])
@require_login(role='user')
def delete_attendee():
    uid = current_user()['id']
    try:
        aid = int(_body().get('attendee_id'))
        execute("DELETE FROM attendee WHERE attendee_id=%s AND user_id=%s", (aid, uid))
        return ok(msg='购票人已删除')
    except (TypeError, ValueError):
        return fail('购票人编号不正确')
    except pymysql.err.IntegrityError:
        return fail('删除失败：该购票人已被订单引用，为保留历史订单不可删除')
