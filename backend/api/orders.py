# -*- coding: utf-8 -*-
"""订单与购票接口：我的订单、购票（核心事务）。"""
from datetime import datetime
import uuid

import pymysql
from flask import Blueprint, request, session

from db import q, get_conn
from .helpers import ok, fail, require_login, current_user

orders_bp = Blueprint('api_orders', __name__)


@orders_bp.route('/orders')
@require_login(role='user')
def list_orders():
    uid = current_user()['id']
    orders = q("""SELECT * FROM v_order_detail
                  WHERE order_id IN (SELECT order_id FROM ticket_order WHERE user_id=%s)
                  ORDER BY create_time DESC""", (uid,))
    items = q("""SELECT oi.order_id, oi.unit_price, a.attendee_name, a.id_type, a.id_no
                 FROM order_item oi JOIN attendee a ON a.attendee_id=oi.attendee_id
                 WHERE oi.order_id IN (SELECT order_id FROM ticket_order WHERE user_id=%s)
                 ORDER BY oi.item_id""", (uid,))
    items_by_order = {}
    for it in items:
        it['unit_price'] = float(it['unit_price'])
        items_by_order.setdefault(it['order_id'], []).append(it)
    for o in orders:
        o['total_amount'] = float(o['total_amount'])
        o['items'] = items_by_order.get(o['order_id'], [])
    return ok({'list': orders})


class BuyError(Exception):
    pass


@orders_bp.route('/buy', methods=['POST'])
@require_login(role='user')
def buy():
    uid = current_user()['id']
    body = request.get_json(silent=True) or {}
    if not body:
        # 兼容表单提交
        body = {k: v for k, v in request.form.items()}
        body['attendee_ids'] = request.form.getlist('attendee_ids')
    session_id = int(body.get('session_id') or 0)
    tier_id = int(body.get('tier_id') or 0)
    count = int(body.get('count') or 0)
    address_id = int(body.get('address_id') or 0)
    attendee_ids = [int(x) for x in (body.get('attendee_ids') or [])]
    show_id = int(body.get('show_id') or 0)

    def log_fail(reason):
        try:
            from db import execute
            execute("""INSERT INTO purchase_request(user_id,session_id,tier_id,ticket_count,result,fail_reason)
                       VALUES(%s,%s,%s,%s,0,%s)""",
                    (uid, session_id or 0, tier_id or 0, count, reason))
        except Exception:
            pass

    if not (show_id and session_id and tier_id and address_id and 1 <= count <= 6):
        log_fail('表单不完整')
        return fail('请完整选择场次、票档、票数(1-6)和收货地址')
    if len(attendee_ids) != count:
        log_fail('购票人数量与票数不一致')
        return fail('购票人数量必须与票数一致（每人限购 1 张）')

    conn = get_conn()
    try:
        cur = conn.cursor()
        conn.begin()
        cur.execute("""INSERT INTO purchase_request(user_id,session_id,tier_id,ticket_count,result,fail_reason)
                       VALUES(%s,%s,%s,%s,0,'处理中')""", (uid, session_id, tier_id, count))
        req_id = cur.lastrowid
        # 锁定场次并同时核对 show_id，防止拼接不同演出的参数。
        cur.execute("""SELECT s.show_id, se.show_time, se.sale_start, se.sale_status
                       FROM show_session se
                       JOIN show_item s ON s.show_id=se.show_id
                       WHERE se.session_id=%s AND se.show_id=%s
                       FOR UPDATE""", (session_id, show_id))
        se = cur.fetchone()
        if not se:
            raise BuyError('演出、场次信息不匹配')
        now = datetime.now()
        if se['show_time'] <= now:
            raise BuyError('该场次已结束')
        if se['sale_status'] != 2:
            if se['sale_status'] == 4:
                raise BuyError('该场次已结束')
            if se['sale_status'] == 3:
                raise BuyError('该场次已售罄')
            raise BuyError('该场次当前暂未开放购票')
        if se['sale_start'] > now:
            raise BuyError('演出尚未开售（预售中）')
        # 票档必须属于已锁定的场次；锁定票档行后再扣库存。
        cur.execute("""SELECT tier_id, price, total_seats, sold_seats
                       FROM ticket_tier
                       WHERE tier_id=%s AND session_id=%s
                       FOR UPDATE""", (tier_id, session_id))
        tier = cur.fetchone()
        if not tier:
            raise BuyError('票档不属于该演出场次')
        remain = tier['total_seats'] - tier['sold_seats']
        if remain <= 0:
            raise BuyError('该场次已售罄')
        if remain < count:
            raise BuyError('余票不足，购票失败')
        cur.execute("SELECT 1 FROM shipping_address WHERE address_id=%s AND user_id=%s", (address_id, uid))
        if not cur.fetchone():
            raise BuyError('收货信息无效')
        for aid in attendee_ids:
            cur.execute("SELECT 1 FROM attendee WHERE attendee_id=%s AND user_id=%s", (aid, uid))
            if not cur.fetchone():
                raise BuyError('购票人信息无效')
        for aid in attendee_ids:
            cur.execute("""SELECT a.attendee_name FROM order_item oi
                           JOIN ticket_order o ON o.order_id=oi.order_id
                           JOIN attendee a ON a.attendee_id=oi.attendee_id
                           WHERE oi.attendee_id=%s AND oi.session_id=%s
                             AND o.order_status IN (1,2) LIMIT 1""", (aid, session_id))
            hit = cur.fetchone()
            if hit:
                raise BuyError('超出限购：购票人【%s】已购买该场次门票（每人限购 1 张）'
                               % hit['attendee_name'])
        cur.execute("""UPDATE ticket_tier SET sold_seats=sold_seats+%s
                       WHERE tier_id=%s AND session_id=%s
                         AND total_seats-sold_seats>=%s""", (count, tier_id, session_id, count))
        if cur.rowcount == 0:
            raise BuyError('余票不足，购票失败')
        price = float(tier['price'])
        # 32 字符以内的 UUID 业务号，避免时间戳+短随机数在并发下碰撞。
        order_no = None
        for _ in range(3):
            candidate = 'NO' + uuid.uuid4().hex[:30].upper()
            try:
                cur.execute("""INSERT INTO ticket_order(order_no,user_id,session_id,tier_id,address_id,
                                 ticket_count,total_amount,order_status)
                               VALUES(%s,%s,%s,%s,%s,%s,%s,1)""",
                            (candidate, uid, session_id, tier_id, address_id, count, price * count))
                order_no = candidate
                break
            except pymysql.err.IntegrityError as e:
                if not e.args or e.args[0] != 1062:
                    raise
        if order_no is None:
            raise BuyError('订单号生成冲突，请稍后重试')
        oid = cur.lastrowid
        for aid in attendee_ids:
            cur.execute("""INSERT INTO order_item(order_id,tier_id,attendee_id,session_id,unit_price)
                           VALUES(%s,%s,%s,%s,%s)""", (oid, tier_id, aid, session_id, price))
        cur.execute("UPDATE ticket_order SET order_status=2, pay_time=NOW() WHERE order_id=%s", (oid,))
        cur.execute("UPDATE purchase_request SET result=1, fail_reason=NULL WHERE request_id=%s", (req_id,))
        conn.commit()
        return ok({'order_no': order_no, 'count': count, 'amount': price * count},
                  msg='购票成功！订单号 %s，共 %s 张，金额 ¥%.2f' % (order_no, count, price * count))
    except BuyError as e:
        conn.rollback()
        log_fail(str(e))
        return fail('购票失败：%s（请求已记录）' % e)
    except pymysql.err.IntegrityError:
        conn.rollback()
        log_fail('超出限购（唯一约束拦截）')
        return fail('购票失败：超出限购，每位购票人同一场次限购 1 张（请求已记录）')
    except Exception as e:
        conn.rollback()
        log_fail('系统异常：%s' % e)
        return fail('购票失败：系统异常，请稍后重试（请求已记录）')
    finally:
        conn.close()
