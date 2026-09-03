# -*- coding: utf-8 -*-
"""
演出门票销售系统 —— Flask 演示系统
连接 ticket_sales 数据库（由 ddl.sql + seed_data.sql + views.sql 建库）。
运行：python app.py，浏览器打开 http://127.0.0.1:5000
演示账号：用户 zhang_san / li_si / wang_wu / zhao_liu / chen_qi，管理员 admin；
         口令统一 123456（seed 中为占位哈希，详见 README）。
"""
import os
import random
from datetime import datetime, date, timedelta

import pymysql
from pymysql.cursors import DictCursor
from flask import (Flask, request, session, redirect, url_for,
                   render_template, flash, jsonify, g)

from config import DB_CONFIG, SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY

PLACEHOLDER_HASH = '$2b$10$0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ'
ID_TYPE_NAMES = {1: '身份证', 2: '护照', 3: '港澳通行证', 4: '台胞证', 5: '军官证'}
STATUS_NAMES = {1: '预售中', 2: '售票中', 3: '售罄'}
ORDER_STATUS_NAMES = {1: '待支付', 2: '已支付', 3: '已取消', 4: '已退款'}


# ---------------------------------------------------------------------------
# 数据库连接
# ---------------------------------------------------------------------------
def get_conn():
    return pymysql.connect(cursorclass=DictCursor, autocommit=False, **DB_CONFIG)


def q(sql, args=(), one=False):
    """查询（只读，自动关连接）。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        conn.close()


def execute(sql, args=()):
    """写操作（自动提交），返回 lastrowid。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            conn.commit()
            return cur.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 登录与权限
# ---------------------------------------------------------------------------
def verify_password(stored_hash, input_pw):
    """seed 中口令为占位哈希时，演示口令 123456 放行；真实 bcrypt 哈希走 werkzeug 校验。"""
    if not stored_hash:
        return False
    if stored_hash == PLACEHOLDER_HASH:
        return input_pw == '123456'
    try:
        from werkzeug.security import check_password_hash
        return check_password_hash(stored_hash, input_pw)
    except Exception:
        return False


def current_user():
    return session.get('user')


def login_required(role=None):
    def deco(fn):
        from functools import wraps
        @wraps(fn)
        def wrapper(*args, **kwargs):
            u = current_user()
            if not u:
                flash('请先登录')
                return redirect(url_for('login', next=request.path))
            if role and u['role'] != role:
                flash('无权访问该页面')
                return redirect(url_for('show_list'))
            return fn(*args, **kwargs)
        return wrapper
    return deco


@app.context_processor
def inject_globals():
    return {'me': current_user(),
            'STATUS_NAMES': STATUS_NAMES,
            'ORDER_STATUS_NAMES': ORDER_STATUS_NAMES,
            'ID_TYPE_NAMES': ID_TYPE_NAMES}


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        role = request.form.get('role') or 'user'
        if role == 'admin':
            row = q("SELECT * FROM admin WHERE username=%s", (username,), one=True)
            if row and verify_password(row['password_hash'], password):
                session['user'] = {'role': 'admin', 'id': row['admin_id'],
                                   'name': row['real_name'] or row['username']}
                flash('管理员登录成功')
                return redirect(url_for('admin_shows'))
        else:
            row = q("SELECT * FROM app_user WHERE username=%s", (username,), one=True)
            if row and row['status'] == 1 and verify_password(row['password_hash'], password):
                session['user'] = {'role': 'user', 'id': row['user_id'],
                                   'name': row['username']}
                flash('登录成功，欢迎 %s' % row['username'])
                return redirect(request.args.get('next') or url_for('show_list'))
        flash('登录失败：用户名或密码错误')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('已退出登录')
    return redirect(url_for('show_list'))


# ---------------------------------------------------------------------------
# 游客/用户：演出列表、详情
# ---------------------------------------------------------------------------
@app.route('/')
def show_list():
    city_id = request.args.get('city_id', type=int)
    cat_id = request.args.get('category_id', type=int)
    keyword = (request.args.get('keyword') or '').strip()
    sql = "SELECT * FROM v_show_list WHERE 1=1"
    args = []
    if city_id:
        sql += " AND city_id=%s"; args.append(city_id)
    if cat_id:
        sql += " AND category_id=%s"; args.append(cat_id)
    if keyword:
        sql += " AND show_name LIKE %s"; args.append('%%%s%%' % keyword)
    sql += " ORDER BY show_id"
    shows = q(sql, args)
    cities = q("SELECT * FROM city ORDER BY city_id")
    cats = q("SELECT * FROM category ORDER BY category_id")
    return render_template('shows.html', shows=shows, cities=cities, cats=cats,
                           city_id=city_id, cat_id=cat_id, keyword=keyword)


@app.route('/show/<int:show_id>')
def show_detail(show_id):
    show = q("""SELECT s.*, c.city_name, cat.category_name
                FROM show_item s
                JOIN city c ON c.city_id=s.city_id
                JOIN category cat ON cat.category_id=s.category_id
                WHERE s.show_id=%s""", (show_id,), one=True)
    if not show:
        flash('演出不存在')
        return redirect(url_for('show_list'))
    images = q("SELECT * FROM show_image WHERE show_id=%s ORDER BY sort_no, image_id", (show_id,))
    sessions = q("""SELECT se.*, v.venue_name, v.address,
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
        tiers_by_session.setdefault(t['session_id'], []).append(t)
    # 演出级票价区间与售票状态（来自列表视图聚合）
    pr = q("SELECT min_price, max_price, show_status FROM v_show_list WHERE show_id=%s",
           (show_id,), one=True) or {}
    addresses = attendees = None
    me = current_user()
    if me and me['role'] == 'user':
        addresses = q("SELECT * FROM shipping_address WHERE user_id=%s ORDER BY is_default DESC, address_id",
                      (me['id'],))
        attendees = q("SELECT * FROM attendee WHERE user_id=%s ORDER BY attendee_id", (me['id'],))
    return render_template('show_detail.html', show=show, images=images,
                           sessions=sessions, tiers_by_session=tiers_by_session,
                           addresses=addresses, attendees=attendees, pr=pr)


# ---------------------------------------------------------------------------
# 用户：购票（核心事务）
# ---------------------------------------------------------------------------
class BuyError(Exception):
    pass


@app.route('/buy', methods=['POST'])
@login_required(role='user')
def buy():
    uid = current_user()['id']
    session_id = request.form.get('session_id', type=int)
    tier_id = request.form.get('tier_id', type=int)
    count = request.form.get('count', type=int) or 0
    address_id = request.form.get('address_id', type=int)
    attendee_ids = request.form.getlist('attendee_ids')

    def log_fail(reason):
        try:
            execute("""INSERT INTO purchase_request(user_id,session_id,tier_id,ticket_count,result,fail_reason)
                       VALUES(%s,%s,%s,%s,0,%s)""",
                    (uid, session_id or 0, tier_id or 0, count, reason))
        except Exception:
            pass

    if not (session_id and tier_id and address_id and 1 <= count <= 6):
        log_fail('表单不完整：未完整选择场次/票档/票数(1-6)/收货地址')
        flash('购票失败：请完整选择场次、票档、票数(1-6)和收货地址')
        return redirect(url_for('show_detail', show_id=request.form.get('show_id', 1)))
    if len(attendee_ids) != count:
        log_fail('购票人数量(%s)与票数(%s)不一致' % (len(attendee_ids), count))
        flash('购票失败：购票人数量必须与票数一致（每人限购 1 张，共选 %s 位）' % count)
        return redirect(url_for('show_detail', show_id=request.form.get('show_id', 1)))

    conn = get_conn()
    try:
        cur = conn.cursor()
        conn.begin()
        # ① 请求留痕
        cur.execute("""INSERT INTO purchase_request(user_id,session_id,tier_id,ticket_count,result,fail_reason)
                       VALUES(%s,%s,%s,%s,0,'处理中')""", (uid, session_id, tier_id, count))
        req_id = cur.lastrowid
        # ② 场次状态校验（预售中不可买）
        cur.execute("SELECT sale_status, sale_start FROM show_session WHERE session_id=%s", (session_id,))
        se = cur.fetchone()
        if not se:
            raise BuyError('演出场次不存在')
        if se['sale_status'] == 1 or se['sale_start'] > datetime.now():
            raise BuyError('演出尚未开售（预售中），请等待开票')
        if se['sale_status'] == 3:
            raise BuyError('该场次已售罄')
        # ③ 归属校验：地址、购票人必须属于当前用户
        cur.execute("SELECT 1 FROM shipping_address WHERE address_id=%s AND user_id=%s", (address_id, uid))
        if not cur.fetchone():
            raise BuyError('收货信息无效')
        for aid in attendee_ids:
            cur.execute("SELECT 1 FROM attendee WHERE attendee_id=%s AND user_id=%s", (int(aid), uid))
            if not cur.fetchone():
                raise BuyError('购票人信息无效')
        # ④ 限购校验：每位购票人该场次未持票（订单明细唯一键兜底）
        for aid in attendee_ids:
            cur.execute("""SELECT 1 FROM order_item oi
                           JOIN ticket_order o ON o.order_id=oi.order_id
                           WHERE oi.attendee_id=%s AND oi.session_id=%s
                             AND o.order_status IN (1,2) LIMIT 1""", (int(aid), session_id))
            if cur.fetchone():
                cur.execute("SELECT attendee_name FROM attendee WHERE attendee_id=%s", (int(aid),))
                name = cur.fetchone()
                raise BuyError('超出限购：购票人【%s】已购买该场次门票（每人限购 1 张）'
                               % (name['attendee_name'] if name else aid))
        # ⑤ 原子扣减余票
        cur.execute("""UPDATE ticket_tier SET sold_seats=sold_seats+%s
                       WHERE tier_id=%s AND total_seats-sold_seats>=%s""", (count, tier_id, count))
        if cur.rowcount == 0:
            raise BuyError('余票不足，购票失败（该票档剩余票数少于 %s 张）' % count)
        # ⑥ 生成订单与明细（单价快照）
        cur.execute("SELECT price FROM ticket_tier WHERE tier_id=%s", (tier_id,))
        price = cur.fetchone()['price']
        order_no = 'NO' + datetime.now().strftime('%Y%m%d%H%M%S') + '%04d' % random.randint(0, 9999)
        cur.execute("""INSERT INTO ticket_order(order_no,user_id,session_id,tier_id,address_id,
                         ticket_count,total_amount,order_status)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,1)""",
                    (order_no, uid, session_id, tier_id, address_id, count, price * count))
        oid = cur.lastrowid
        for aid in attendee_ids:
            cur.execute("""INSERT INTO order_item(order_id,tier_id,attendee_id,session_id,unit_price)
                           VALUES(%s,%s,%s,%s,%s)""", (oid, tier_id, int(aid), session_id, price))
        # ⑦ 支付成功（触发器 trg_order_paid 自动累加 sales_daily）
        cur.execute("UPDATE ticket_order SET order_status=2, pay_time=NOW() WHERE order_id=%s", (oid,))
        cur.execute("UPDATE purchase_request SET result=1, fail_reason=NULL WHERE request_id=%s", (req_id,))
        conn.commit()
        flash('购票成功！订单号 %s，共 %s 张，金额 ¥%.2f' % (order_no, count, price * count))
    except BuyError as e:
        conn.rollback()
        log_fail(str(e))
        flash('购票失败：%s（请求已记录）' % e)
    except pymysql.err.IntegrityError:
        conn.rollback()
        log_fail('超出限购（数据库唯一约束拦截）')
        flash('购票失败：超出限购，每位购票人同一场次限购 1 张（请求已记录）')
    except Exception as e:
        conn.rollback()
        log_fail('系统异常：%s' % e)
        flash('购票失败：系统异常，请稍后重试（请求已记录）')
    finally:
        conn.close()
    return redirect(url_for('show_detail', show_id=request.form.get('show_id', 1)))


# ---------------------------------------------------------------------------
# 用户：我的订单
# ---------------------------------------------------------------------------
@app.route('/orders')
@login_required(role='user')
def orders():
    uid = current_user()['id']
    rows = q("""SELECT * FROM v_order_detail
                WHERE order_id IN (SELECT order_id FROM ticket_order WHERE user_id=%s)
                ORDER BY create_time DESC""", (uid,))
    items = q("""SELECT oi.order_id, oi.unit_price, a.attendee_name, a.id_type, a.id_no
                 FROM order_item oi JOIN attendee a ON a.attendee_id=oi.attendee_id
                 WHERE oi.order_id IN (SELECT order_id FROM ticket_order WHERE user_id=%s)
                 ORDER BY oi.item_id""", (uid,))
    items_by_order = {}
    for it in items:
        items_by_order.setdefault(it['order_id'], []).append(it)
    return render_template('orders.html', orders=rows, items_by_order=items_by_order)


# ---------------------------------------------------------------------------
# 用户：收货信息管理
# ---------------------------------------------------------------------------
@app.route('/addresses', methods=['GET', 'POST'])
@login_required(role='user')
def addresses():
    uid = current_user()['id']
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            execute("""INSERT INTO shipping_address(user_id,receiver_name,phone,address_detail,is_default)
                       VALUES(%s,%s,%s,%s,%s)""",
                    (uid, request.form.get('receiver_name'), request.form.get('phone'),
                     request.form.get('address_detail'), int(request.form.get('is_default') or 0)))
            flash('收货信息已添加')
        elif action == 'delete':
            execute("DELETE FROM shipping_address WHERE address_id=%s AND user_id=%s",
                    (int(request.form.get('address_id')), uid))
            flash('收货信息已删除')
        return redirect(url_for('addresses'))
    rows = q("SELECT * FROM shipping_address WHERE user_id=%s ORDER BY is_default DESC, address_id", (uid,))
    return render_template('addresses.html', addresses=rows)


# ---------------------------------------------------------------------------
# 用户：常用购票人管理
# ---------------------------------------------------------------------------
@app.route('/attendees', methods=['GET', 'POST'])
@login_required(role='user')
def attendees():
    uid = current_user()['id']
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            try:
                execute("""INSERT INTO attendee(user_id,attendee_name,id_type,id_no)
                           VALUES(%s,%s,%s,%s)""",
                        (uid, request.form.get('attendee_name'),
                         int(request.form.get('id_type')), request.form.get('id_no')))
                flash('购票人已添加')
            except pymysql.err.IntegrityError:
                flash('添加失败：该证件类型+证件号已存在（同一用户不可重复）')
        elif action == 'delete':
            try:
                execute("DELETE FROM attendee WHERE attendee_id=%s AND user_id=%s",
                        (int(request.form.get('attendee_id')), uid))
                flash('购票人已删除')
            except pymysql.err.IntegrityError:
                flash('删除失败：该购票人已被订单引用，为保留历史订单不可删除')
        return redirect(url_for('attendees'))
    rows = q("SELECT * FROM attendee WHERE user_id=%s ORDER BY attendee_id", (uid,))
    return render_template('attendees.html', attendees=rows)


# ---------------------------------------------------------------------------
# 管理员：演出管理
# ---------------------------------------------------------------------------
@app.route('/admin')
@login_required(role='admin')
def admin_index():
    return redirect(url_for('admin_shows'))


@app.route('/admin/shows')
@login_required(role='admin')
def admin_shows():
    shows = q("SELECT * FROM v_show_list ORDER BY show_id DESC")
    cities = q("SELECT * FROM city ORDER BY city_id")
    cats = q("SELECT * FROM category ORDER BY category_id")
    venues = q("SELECT * FROM venue ORDER BY venue_id")
    return render_template('admin_shows.html', shows=shows, cities=cities, cats=cats, venues=venues)


@app.route('/admin/show/create', methods=['POST'])
@login_required(role='admin')
def admin_show_create():
    admin_id = current_user()['id']
    try:
        sid = execute("""INSERT INTO show_item(show_name,category_id,city_id,poster_url,description,admin_id)
                         VALUES(%s,%s,%s,%s,%s,%s)""",
                      (request.form.get('show_name'), int(request.form.get('category_id')),
                       int(request.form.get('city_id')), request.form.get('poster_url') or '',
                       request.form.get('description') or '', admin_id))
        flash('演出已创建（show_id=%s），可继续添加场次和票档' % sid)
    except Exception as e:
        flash('创建失败：%s' % e)
    return redirect(url_for('admin_shows'))


@app.route('/admin/show/<int:show_id>/update', methods=['POST'])
@login_required(role='admin')
def admin_show_update(show_id):
    execute("""UPDATE show_item SET show_name=%s, category_id=%s, city_id=%s,
               poster_url=%s, description=%s WHERE show_id=%s""",
            (request.form.get('show_name'), int(request.form.get('category_id')),
             int(request.form.get('city_id')), request.form.get('poster_url') or '',
             request.form.get('description') or '', show_id))
    flash('演出信息已更新')
    return redirect(url_for('admin_show_edit', show_id=show_id))


@app.route('/admin/show/<int:show_id>/delete', methods=['POST'])
@login_required(role='admin')
def admin_show_delete(show_id):
    try:
        execute("DELETE FROM show_item WHERE show_id=%s", (show_id,))
        flash('演出及其场次、票档、图片已级联删除')
    except pymysql.err.IntegrityError:
        flash('删除失败：该演出已有订单，为保留销售数据不可删除')
    return redirect(url_for('admin_shows'))


@app.route('/admin/show/<int:show_id>')
@login_required(role='admin')
def admin_show_edit(show_id):
    show = q("""SELECT s.*, c.city_name, cat.category_name
                FROM show_item s
                JOIN city c ON c.city_id=s.city_id
                JOIN category cat ON cat.category_id=s.category_id
                WHERE s.show_id=%s""", (show_id,), one=True)
    if not show:
        flash('演出不存在')
        return redirect(url_for('admin_shows'))
    sessions = q("""SELECT se.*, v.venue_name FROM show_session se
                    JOIN venue v ON v.venue_id=se.venue_id
                    WHERE se.show_id=%s ORDER BY se.show_time""", (show_id,))
    tiers = q("""SELECT t.*, t.total_seats-t.sold_seats AS remain FROM ticket_tier t
                 WHERE t.session_id IN (SELECT session_id FROM show_session WHERE show_id=%s)
                 ORDER BY t.session_id, t.price DESC""", (show_id,))
    tiers_by_session = {}
    for t in tiers:
        tiers_by_session.setdefault(t['session_id'], []).append(t)
    venues = q("SELECT * FROM venue ORDER BY venue_id")
    cities = q("SELECT * FROM city ORDER BY city_id")
    cats = q("SELECT * FROM category ORDER BY category_id")
    return render_template('admin_show_edit.html', show=show, sessions=sessions,
                           tiers_by_session=tiers_by_session, venues=venues,
                           cities=cities, cats=cats)


@app.route('/admin/session/create', methods=['POST'])
@login_required(role='admin')
def admin_session_create():
    show_id = int(request.form.get('show_id'))
    show_time = (request.form.get('show_time') or '').replace('T', ' ')
    sale_start = (request.form.get('sale_start') or '').replace('T', ' ')
    try:
        execute("""INSERT INTO show_session(show_id,venue_id,show_time,sale_start,sale_status)
                   VALUES(%s,%s,%s,%s,1)""",
                (show_id, int(request.form.get('venue_id')), show_time, sale_start))
        flash('场次已添加（默认“预售中”，到开售时间后由事件自动推进）')
    except pymysql.err.IntegrityError as e:
        flash('场次添加失败：%s' % ('该演出已存在相同开演时间' if 'uk_session' in str(e) else e))
    except Exception as e:
        flash('场次添加失败：%s' % e)
    return redirect(url_for('admin_show_edit', show_id=show_id))


@app.route('/admin/tier/create', methods=['POST'])
@login_required(role='admin')
def admin_tier_create():
    show_id = int(request.form.get('show_id'))
    session_id = int(request.form.get('session_id'))
    try:
        execute("""INSERT INTO ticket_tier(session_id,tier_name,price,total_seats,sold_seats)
                   VALUES(%s,%s,%s,%s,0)""",
                (session_id, request.form.get('tier_name'),
                 float(request.form.get('price')), int(request.form.get('total_seats'))))
        flash('票档已添加')
    except pymysql.err.IntegrityError as e:
        flash('票档添加失败：%s' % ('同一场次已存在同名票档' if 'uk_tier' in str(e) else e))
    except Exception as e:
        flash('票档添加失败：%s' % e)
    return redirect(url_for('admin_show_edit', show_id=show_id))


# ---------------------------------------------------------------------------
# 管理员：销售统计（图表数据）
# ---------------------------------------------------------------------------
@app.route('/admin/stats')
@login_required(role='admin')
def admin_stats():
    today = date.today()
    start = request.args.get('start') or (today - timedelta(days=29)).isoformat()
    end = request.args.get('end') or today.isoformat()
    return render_template('admin_stats.html', start=start, end=end)


@app.route('/admin/stats/data')
@login_required(role='admin')
def admin_stats_data():
    start = request.args.get('start')
    end = request.args.get('end')
    end_full = end + ' 23:59:59'
    daily = q("""SELECT DATE(pay_time) AS d, COUNT(*) AS orders,
                        SUM(ticket_count) AS tickets, SUM(total_amount) AS amount
                 FROM ticket_order
                 WHERE order_status=2 AND pay_time BETWEEN %s AND %s
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
    return jsonify({
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


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
