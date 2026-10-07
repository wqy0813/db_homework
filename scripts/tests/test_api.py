# -*- coding: utf-8 -*-
"""
自动化功能测试（API 层）：覆盖测试文档 T1-T13 的功能逻辑。
运行：python scripts/tests/test_api.py
结果：stdout 打印 PASS/FAIL 明细；同时写入 docs/test-results/test_api_results.json
说明：T6 购票成功会产生 1 条真实订单（文档附录提供 sql/seed/seed_data.sql 可恢复）。
"""
import sys
import io
import json
import time
import os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import pymysql
from pymysql.cursors import DictCursor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))
from config import DB_CONFIG  # noqa: E402

BASE = 'http://127.0.0.1:5000/api'
RESULTS = []
PASS = 0
FAIL = 0


def record(case, name, passed, detail=''):
    global PASS, FAIL
    if passed:
        PASS += 1
    else:
        FAIL += 1
    RESULTS.append({'case': case, 'name': name, 'pass': bool(passed), 'detail': detail})
    print('%s %-12s %-40s %s' % ('PASS' if passed else 'FAIL', case, name, detail))


class Client:
    def __init__(self):
        self.s = requests.Session()

    def call(self, method, path, **kw):
        r = self.s.request(method, BASE + path, timeout=15, **kw)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'code': -1, 'msg': r.text[:200]}

    def get(self, path, **kw):
        return self.call('GET', path, **kw)

    def post(self, path, **kw):
        return self.call('POST', path, **kw)

    def login(self, role, username, password):
        return self.post('/login', json={'role': role, 'username': username, 'password': password})


guest = Client()
user = Client()
admin = Client()

# ============================================================
# T1 首页-巡演列表展示
# ============================================================
def t1():
    code, d = guest.get('/series')
    ok = code == 200 and d.get('code') == 0
    lst = d.get('data', {}).get('list', []) if ok else []
    record('T1.1', '首页巡演列表(标题+卡片数据)', ok and len(lst) > 0,
           'series总数=%d' % len(lst))
    # 卡片字段：poster_url, category_name, main_artist, city_count, station_count, show_dates, min/max price
    fields_ok = all(all(k in s for k in
                        ('series_id', 'series_name', 'poster_url', 'category_name',
                         'main_artist', 'city_count', 'station_count', 'min_price', 'max_price'))
                    for s in lst[:20]) if lst else False
    record('T1.1b', '巡演卡片字段齐全', fields_ok)

    names = [s['series_name'] for s in lst]
    record('T1.2', '演唱会类(周杰伦/张学友/林俊杰)存在', all(k in ' '.join(names) for k in ['周杰伦', '张学友', '林俊杰']))
    record('T1.3', '体育类(CBA/排球超级联赛)存在', any('CBA' in n for n in names) and any('排球' in n for n in names))
    record('T1.4', '话剧/展览/音乐会/舞蹈存在', all(any(k in n for n in names) for k in ['猫', '莫奈', '郎朗', '只此青绿']))

    # 单场演出
    code2, d2 = guest.get('/shows')
    others = [x for x in d2.get('data', {}).get('list', []) if not x.get('series_id')]
    record('T1.5', '其他单场演出(威尼斯商人)展示', any('威尼斯商人' in x['show_name'] for x in others),
           '单场数=%d' % len(others))


# ============================================================
# T2 巡演筛选
# ============================================================
def t2():
    # 演唱会类型
    code, d = guest.get('/series', params={'category_id': 1})
    lst = d.get('data', {}).get('list', [])
    record('T2.1', '类型=演唱会只显示演唱会', code == 200 and len(lst) > 0 and all(s['category_name'] == '演唱会' for s in lst),
           'count=%d' % len(lst))
    # 城市=北京
    code, d = guest.get('/series', params={'city_id': 1})
    lst = d.get('data', {}).get('list', [])
    rec = code == 200 and len(lst) > 0
    # 通过 series 详情校验每个都含北京站
    all_bj = True
    for s in lst[:5]:
        _, sd = guest.get('/series/%d' % s['series_id'])
        if not any(st['city_name'] == '北京' for st in sd.get('data', {}).get('stations', [])):
            all_bj = False
            break
    record('T2.2', '城市=北京只显示北京有站的巡演', rec and all_bj, 'count=%d' % len(lst))
    # 关键词 周杰伦
    code, d = guest.get('/series', params={'keyword': '周杰伦'})
    lst = d.get('data', {}).get('list', [])
    record('T2.3', '关键词"周杰伦"', code == 200 and len(lst) == 1 and '周杰伦' in lst[0]['series_name'],
           'count=%d names=%s' % (len(lst), [s['series_name'] for s in lst]))
    # 关键词 排球
    code, d = guest.get('/series', params={'keyword': '排球'})
    lst = d.get('data', {}).get('list', [])
    record('T2.4', '关键词"排球"', code == 200 and len(lst) == 1 and '排球' in lst[0]['series_name'],
           'count=%d names=%s' % (len(lst), [s['series_name'] for s in lst]))
    # 组合：演唱会+北京
    code, d = guest.get('/series', params={'category_id': 1, 'city_id': 1})
    lst = d.get('data', {}).get('list', [])
    all_ok = len(lst) > 0 and all(s['category_name'] == '演唱会' for s in lst)
    all_bj2 = True
    for s in lst[:8]:
        _, sd = guest.get('/series/%d' % s['series_id'])
        if not any(st['city_name'] == '北京' for st in sd.get('data', {}).get('stations', [])):
            all_bj2 = False
            break
    record('T2.5', '组合筛选:演唱会+北京', code == 200 and all_ok and all_bj2, 'count=%d' % len(lst))


# ============================================================
# T3 巡演详情页（展开各站）
# ============================================================
def t3():
    code, d = guest.get('/series/69')  # 周杰伦
    data = d.get('data', {})
    ser = data.get('series') or {}
    sts = data.get('stations') or []
    record('T3.1', '周杰伦巡演详情', code == 200 and ser.get('series_name', '').find('周杰伦') >= 0
           and ser.get('main_artist') == '周杰伦', 'artist=%s' % ser.get('main_artist'))
    record('T3.2', '城市站列表(城市/场次/日期/票价)', len(sts) >= 5
           and all(st.get('city_name') and st.get('session_count') is not None and st.get('min_price') for st in sts),
           'stations=%d' % len(sts))
    bj = [st for st in sts if st['city_name'] == '北京']
    record('T3.3', '点北京站→演出详情(show_id 可访问)', len(bj) == 1 and bj[0]['show_id'] is not None,
           'beijing show_id=%s' % (bj[0]['show_id'] if bj else None))


# ============================================================
# T4 演出详情页（某站）
# ============================================================
def future_sale_target(attendee_id=None):
    """从当前数据库选择真实的未来开售场次，避免依赖过期种子日期。"""
    conn = pymysql.connect(cursorclass=DictCursor, **DB_CONFIG)
    try:
        sql = """
            SELECT se.show_id, se.session_id, t.tier_id
            FROM show_session se
            JOIN ticket_tier t ON t.session_id=se.session_id
            WHERE se.sale_start > NOW() AND t.total_seats > t.sold_seats
        """
        args = []
        if attendee_id is not None:
            sql += """
              AND NOT EXISTS (
                SELECT 1 FROM order_item oi
                JOIN ticket_order o ON o.order_id=oi.order_id
                WHERE oi.attendee_id=%s AND oi.session_id=se.session_id
                  AND o.order_status IN (1,2)
              )
            """
            args.append(attendee_id)
        sql += " ORDER BY se.sale_start, se.session_id, t.tier_id LIMIT 1"
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone()
    finally:
        conn.close()


def t4():
    code, d = guest.get('/shows/1')  # 周杰伦北京站
    data = d.get('data', {})
    show = data.get('show') or {}
    summary = data.get('summary') or {}
    sessions = data.get('sessions') or []
    tiers = data.get('tiers') or {}
    images = data.get('images') or []
    record('T4.1', '名称/地点/海报/介绍', code == 200 and show.get('show_name') and show.get('city_name') == '北京'
           and show.get('poster_url') and show.get('description'))
    record('T4.2', '票价区间 ¥380-¥1980', summary.get('min_price') == 380 and summary.get('max_price') == 1980,
           'min=%s max=%s' % (summary.get('min_price'), summary.get('max_price')))
    record('T4.3', '演出介绍图片(多张)', len(images) >= 2, 'images=%d' % len(images))
    record('T4.4', '多个场次，每场时间/场馆/价格/状态', len(sessions) >= 2
           and all(s.get('show_time') and s.get('venue_name') and s.get('min_p') and s.get('sale_status') for s in sessions),
           'sessions=%d' % len(sessions))
    t1_tiers = tiers.get('1') or []
    record('T4.5', '票档表(名称/单价/总票数/已售/余票)',
           len(t1_tiers) >= 4 and all(t.get('tier_name') and t.get('price') and t.get('total_seats')
                                      and t.get('sold_seats') is not None and t.get('remain') is not None for t in t1_tiers),
           'tiers=%d' % len(t1_tiers))
    soldout = [t for t in t1_tiers if t['remain'] == 0]
    record('T4.6', '售罄票档(内场1980 remain=0)', any(t['tier_name'].find('1980') >= 0 and t['remain'] == 0 for t in t1_tiers),
           'soldout=%s' % [(t['tier_name'], t['remain']) for t in soldout])
    pre = [s for s in sessions if s['sale_status'] == 1]
    # 数据库可能是较早生成的快照，show 1 的开售时间已经过去；此时补查
    # 当前库中真实的未来场次，验证接口的预售状态计算。
    if not pre:
        target = future_sale_target()
        if target:
            _, future_data = guest.get('/shows/%s' % target['show_id'])
            pre = [s for s in future_data.get('data', {}).get('sessions', [])
                   if s.get('sale_status') == 1]
    record('T4.7', '预售场次(sale_status=1, sale_start)', len(pre) >= 1 and all(s.get('sale_start') for s in pre),
           'pre=%d' % len(pre))
    on_sale = [s for s in sessions if s['sale_status'] == 2]
    record('T4.8', '未登录(API 游客可读详情，购票需登录)', code == 200 and len(on_sale) >= 1,
           'on_sale=%d' % len(on_sale))
    code, d = guest.get('/series')
    series = d.get('data', {}).get('list', [])
    if series:
        series_id = series[0]['series_id']
        detail_code, detail = guest.get('/series/%s' % series_id)
        stations = detail.get('data', {}).get('stations', [])
        statuses = [station.get('show_status') for station in stations]
        expected = next((status for status in (2, 1, 3, 4) if status in statuses), 3)
        aggregated = next((item.get('status') for item in series
                           if item['series_id'] == series_id), None)
        record('T4.9', '巡演列表与城市站状态按优先级聚合',
               code == 200 and detail_code == 200 and aggregated == expected,
               'series=%s stations=%s aggregate=%s expected=%s'
               % (series_id, statuses, aggregated, expected))
    else:
        record('T4.9', '巡演列表与城市站状态按优先级聚合', False, '没有巡演数据')


# ============================================================
# T5 登录
# ============================================================
def t5():
    code, d = user.login('user', 'zhang_san', '123456')
    record('T5.1', '用户登录成功(zhang_san)', code == 200 and d.get('code') == 0
           and d['data']['user']['name'] == 'zhang_san' and d['data']['user']['role'] == 'user')
    code, d = guest.login('user', 'zhang_san', '1234567')
    record('T5.2', '错误密码提示', code == 200 and d.get('code') == 1
           and '用户名或密码错误' in d.get('msg', ''), 'msg=%s' % d.get('msg'))
    code, d = admin.login('admin', 'admin', '123456')
    record('T5.3', '管理员登录成功(admin)', code == 200 and d.get('code') == 0
           and d['data']['user']['role'] == 'admin')
    # 管理员导航：前端 App.vue 根据 isAdmin 显示 演出管理/销售统计（UI 层验证）
    code, d = admin.post('/logout')
    record('T5.4', '退出登录', code == 200 and d.get('code') == 0)
    code, d = admin.get('/me')
    record('T5.4b', '退出后 /me 未登录(401)', code == 200 and d.get('code') == 401,
           'http=%s code=%s' % (code, d.get('code')))


# ============================================================
# 用户购票（T6/T7）准备：新建购票人
# ============================================================
def setup_user():
    # 用时间戳生成唯一证件号，保证每次运行新建的购票人都是全新的（未买过 session1）
    stamp = str(int(time.time()))[-4:]
    n1 = '11010119990101' + stamp
    n2 = '11010119990102' + stamp
    r1 = user.post('/attendees/add', json={'attendee_name': '测试观众甲', 'id_type': 1, 'id_no': n1})
    r2 = user.post('/attendees/add', json={'attendee_name': '测试观众乙', 'id_type': 1, 'id_no': n2})
    aids = []
    _, d = user.get('/attendees')
    for a in d.get('data', {}).get('list', []):
        if a['attendee_name'] in ('测试观众甲', '测试观众乙') and a['id_no'] in (n1, n2):
            aids.append(a['attendee_id'])
    return r1[1], r2[1], aids


# ============================================================
# T6 购票-成功
# ============================================================
def t6(aids):
    # session 1 售票中，tier 3 看台580，地址1，购票人1位
    code, d = user.post('/buy', json={'show_id': 1, 'session_id': 1, 'tier_id': 3, 'count': 1,
                                      'address_id': 1, 'attendee_ids': [aids[0]]})
    rec = code == 200 and d.get('code') == 0 and d.get('data', {}).get('order_no')
    record('T6.2', '购票成功(看台580×1)', rec, 'msg=%s' % d.get('msg', '')[:60])
    order_no = d.get('data', {}).get('order_no') if rec else None
    # 我的订单最前
    code, d = user.get('/orders')
    lst = d.get('data', {}).get('list', [])
    newest = lst[0] if lst else {}
    record('T6.3', '新订单在最前(已支付)', order_no and lst and newest.get('order_no') == order_no
           and newest.get('order_status') == 2 and newest.get('ticket_count') == 1,
           'status=%s amount=%s' % (newest.get('order_status'), newest.get('total_amount')))
    return order_no


# ============================================================
# T7 购票-失败场景
# ============================================================
def t7(aids):
    # 7.1 票数2但只勾1位购票人
    code, d = user.post('/buy', json={'show_id': 1, 'session_id': 1, 'tier_id': 3, 'count': 2,
                                      'address_id': 1, 'attendee_ids': [aids[0]]})
    record('T7.1', '票数2只勾1位购票人→拒绝', code == 200 and d.get('code') == 1
           and '购票人数量必须与票数一致' in d.get('msg', ''), 'msg=%s' % d.get('msg', '')[:60])
    # 7.2 同购票人再买同场次
    code, d = user.post('/buy', json={'show_id': 1, 'session_id': 1, 'tier_id': 3, 'count': 1,
                                      'address_id': 1, 'attendee_ids': [aids[0]]})
    record('T7.2', '同购票人再买同场次→限购拦截', code == 200 and d.get('code') == 1
           and '超出限购' in d.get('msg', '') and '每人限购 1 张' in d.get('msg', ''),
           'msg=%s' % d.get('msg', '')[:70])
    # 7.3 已售罄票档（内场1980 tier1，用未购票的乙）
    code, d = user.post('/buy', json={'show_id': 1, 'session_id': 1, 'tier_id': 1, 'count': 1,
                                      'address_id': 1, 'attendee_ids': [aids[1]]})
    record('T7.3', '已售罄票档→余票不足', code == 200 and d.get('code') == 1
           and ('余票不足' in d.get('msg', '') or '售罄' in d.get('msg', '')),
           'msg=%s' % d.get('msg', '')[:60])
    # 7.4 选择当前库中确实尚未开售且有余票的场次。
    target = future_sale_target(aids[1])
    payload = {'show_id': target['show_id'], 'session_id': target['session_id'],
               'tier_id': target['tier_id'], 'count': 1, 'address_id': 1,
               'attendee_ids': [aids[1]]} if target else {
                   'show_id': 1, 'session_id': 2, 'tier_id': 5, 'count': 1,
                   'address_id': 1, 'attendee_ids': [aids[1]]}
    code, d = user.post('/buy', json=payload)
    record('T7.4', '预售场次→未开售拦截', code == 200 and d.get('code') == 1
           and '未开售' in d.get('msg', '') or (d.get('code') == 1 and '预售' in d.get('msg', '')),
           'msg=%s' % d.get('msg', '')[:60])
    # 7.5 未登录购票
    code, d = guest.post('/buy', json={'show_id': 1, 'session_id': 1, 'tier_id': 3, 'count': 1,
                                       'address_id': 1, 'attendee_ids': [1]})
    record('T7.5', '未登录购票→401', code == 200 and d.get('code') == 401,
           'http=%s code=%s' % (code, d.get('code')))


# ============================================================
# T8 我的订单
# ============================================================
def t8():
    code, d = user.get('/orders')
    lst = d.get('data', {}).get('list', [])
    fields = ('order_no', 'show_name', 'city_name', 'venue_name', 'show_time',
              'ticket_count', 'total_amount', 'order_status', 'receiver_name', 'phone',
              'address_detail', 'items')
    record('T8.1', '订单表字段齐全', code == 200 and len(lst) > 0
           and all(all(f in o for f in fields) for o in lst[:5]), 'orders=%d' % len(lst))
    record('T8.2', '持票人列(姓名+证件类型)', code == 200 and len(lst) > 0
           and all(o.get('items') and all(i.get('attendee_name') and i.get('id_type') for i in o['items']) for o in lst[:5]))


# ============================================================
# T9 收货信息管理
# ============================================================
def t9():
    code, d = user.post('/addresses/add', json={'receiver_name': '测试收货人', 'phone': '13900001111',
                                                'address_detail': '测试市测试区测试路1号', 'is_default': 0})
    aid1 = d.get('data', {}).get('address_id')
    record('T9.1', '新增收货信息', code == 200 and d.get('code') == 0 and aid1)
    code, d = user.post('/addresses/add', json={'receiver_name': '测试收货人2', 'phone': '13900002222',
                                                'address_detail': '测试市测试区测试路2号', 'is_default': 0})
    aid2 = d.get('data', {}).get('address_id')
    record('T9.2', '新增多条', code == 200 and d.get('code') == 0 and aid2)
    code, d = user.post('/addresses/add', json={'receiver_name': '默认收货人', 'phone': '13900003333',
                                                'address_detail': '测试市默认路3号', 'is_default': 1})
    aid3 = d.get('data', {}).get('address_id')
    code, d = user.get('/addresses')
    lst = d.get('data', {}).get('list', [])
    defrow = [a for a in lst if a.get('address_id') == aid3]
    record('T9.3', '设为默认显示默认标签', code == 200 and defrow and defrow[0]['is_default'] == 1)
    code, d = user.post('/addresses/delete', json={'address_id': aid1})
    code, d = user.get('/addresses')
    lst = d.get('data', {}).get('list', [])
    record('T9.4', '删除收货信息', code == 200 and all(a['address_id'] != aid1 for a in lst))
    # 清理 aid2/aid3
    user.post('/addresses/delete', json={'address_id': aid2})
    user.post('/addresses/delete', json={'address_id': aid3})


# ============================================================
# T10 常用购票人管理
# ============================================================
def t10():
    code, d = user.post('/attendees/add', json={'attendee_name': '测试观众丙', 'id_type': 1,
                                                'id_no': '110101199901013333'})
    aid = d.get('data', {}).get('attendee_id')
    record('T10.1', '新增购票人', code == 200 and d.get('code') == 0 and aid)
    code, d = user.post('/attendees/add', json={'attendee_name': '测试观众丁', 'id_type': 1,
                                                'id_no': '110101199901013333'})
    record('T10.2', '重复证件号→已存在', code == 200 and d.get('code') == 1
           and '已存在' in d.get('msg', ''), 'msg=%s' % d.get('msg', '')[:60])
    code, d = user.post('/attendees/delete', json={'attendee_id': aid})
    record('T10.3', '删除未被引用购票人', code == 200 and d.get('code') == 0)
    code, d = user.post('/attendees/delete', json={'attendee_id': 1})  # 张三已被订单引用
    record('T10.4', '删除被订单引用购票人→拒绝', code == 200 and d.get('code') == 1
           and '已被订单引用' in d.get('msg', ''), 'msg=%s' % d.get('msg', '')[:60])


# ============================================================
# T11 演出管理（管理员）
# ============================================================
def t11():
    admin.login('admin', 'admin', '123456')  # t5.4 已登出，重新登录
    code, d = admin.get('/admin/shows')
    lst = d.get('data', {}).get('list', [])
    fields = ('show_id', 'show_name', 'city_name', 'category_name', 'min_price', 'max_price', 'show_status')
    record('T11.1', '演出列表(字段齐全)', code == 200 and len(lst) > 0
           and all(all(f in s for f in fields) for s in lst[:5]), 'shows=%d' % len(lst))
    # 新建演出（北京/演唱会）
    code, d = admin.post('/admin/shows/create', json={'show_name': '自动化测试演出', 'category_id': 1,
                                                      'city_id': 1, 'poster_url': 'http://x/1.jpg',
                                                      'description': '测试用'})
    sid = d.get('data', {}).get('show_id')
    record('T11.2', '新建演出→返回 show_id', code == 200 and d.get('code') == 0 and sid, 'sid=%s' % sid)
    # 编辑
    code, d = admin.post('/admin/shows/%d/update' % sid, json={'show_name': '自动化测试演出-改',
                                                               'category_id': 1, 'city_id': 1,
                                                               'poster_url': 'http://x/2.jpg',
                                                               'description': '改后'})
    record('T11.3', '编辑演出基本信息', code == 200 and d.get('code') == 0)
    # 详情：场馆按城市过滤（北京无武汉场馆）
    code, d = admin.get('/admin/shows/%d' % sid)
    venues = d.get('data', {}).get('venues', [])
    record('T11.4', '添加场次可选同城场馆', code == 200 and len(venues) >= 1
           and all(v['city_id'] == 1 for v in venues), 'venues=%d' % len(venues))
    record('T11.5', '场馆下拉无武汉场馆', code == 200 and all(v['city_id'] != 7 for v in venues))
    # 添加场次
    code, d = admin.post('/admin/session/create', json={'show_id': sid, 'venue_id': 1,
                                                        'show_time': '2027-05-01 19:30',
                                                        'sale_start': '2027-03-01 10:00'})
    seid = d.get('data', {}).get('session_id')
    record('T11.4b', '添加场次成功', code == 200 and d.get('code') == 0 and seid)
    code, d = admin.get('/admin/shows/%d' % sid)
    created_session = next((s for s in d.get('data', {}).get('sessions', [])
                            if s['session_id'] == seid), {})
    record('T11.4c', '开售时间由后端固定为开演前30天', code == 200
           and created_session.get('sale_start', '').startswith('2027-04-01 19:30'),
           'sale_start=%s' % created_session.get('sale_start'))
    # 添加票档
    code, d = admin.post('/admin/tier/create', json={'session_id': seid, 'tier_name': '测试票档A',
                                                     'price': 100, 'total_seats': 100})
    tid = d.get('data', {}).get('tier_id')
    record('T11.6', '添加票档', code == 200 and d.get('code') == 0 and tid)
    # 删除票档（无订单）
    code, d = admin.post('/admin/tier/%d/delete' % tid)
    record('T11.7', '删除无订单票档', code == 200 and d.get('code') == 0)
    # 再加场次+票档，然后删场次（级联删票档）
    code, d = admin.post('/admin/session/create', json={'show_id': sid, 'venue_id': 2,
                                                        'show_time': '2027-05-02 19:30',
                                                        'sale_start': '2027-04-02 19:30'})
    seid2 = d.get('data', {}).get('session_id')
    admin.post('/admin/tier/create', json={'session_id': seid2, 'tier_name': '测试票档B',
                                           'price': 200, 'total_seats': 50})
    code, d = admin.post('/admin/session/%d/delete' % seid2)
    code, d = admin.get('/admin/shows/%d' % sid)
    remain_tiers = d.get('data', {}).get('tiers', {})
    record('T11.8', '删除无订单场次(票档级联删)', code == 200 and seid2 not in remain_tiers,
           'session2_in_tiers=%s' % (seid2 in remain_tiers))
    # 删除演出（无订单）
    code, d = admin.post('/admin/shows/%d/delete' % sid)
    record('T11.9a', '删除无订单演出', code == 200 and d.get('code') == 0,
           'msg=%s' % d.get('msg', '')[:50])
    # 删除有订单演出（show 1 有订单）
    code, d = admin.post('/admin/shows/1/delete')
    record('T11.9b', '删除有订单演出→拒绝', code == 200 and d.get('code') == 1
           and '不可删除' in d.get('msg', '') and '订单' in d.get('msg', ''), 'msg=%s' % d.get('msg', '')[:60])


# ============================================================
# T12 销售统计
# ============================================================
def t12():
    admin.login('admin', 'admin', '123456')
    code, d = admin.get('/admin/stats', params={'start': '2025-09-01', 'end': '2026-09-03'})
    data = d.get('data', {})
    total = data.get('total', {})
    record('T12.1', '指标卡(订单数/张数/金额)', code == 200 and d.get('code') == 0
           and total.get('orders') > 0 and total.get('tickets') > 0 and total.get('amount') > 0,
           'orders=%s tickets=%s amount=%s' % (total.get('orders'), total.get('tickets'), total.get('amount')))
    record('T12.2', '每日折线数据', code == 200 and len(data.get('daily', [])) > 0
           and all(x.get('d') and x.get('tickets') is not None and x.get('amount') is not None for x in data['daily']),
           'days=%d' % len(data.get('daily', [])))
    record('T12.3', '饼图(各类型销售额)', code == 200 and len(data.get('cats', [])) >= 3
           and all(c.get('name') and c.get('value') for c in data['cats']),
           'cats=%s' % [c['name'] for c in data.get('cats', [])])
    record('T12.4', '柱状图(各城市售票数)', code == 200 and len(data.get('cities', [])) >= 3
           and all(c.get('name') and c.get('tickets') for c in data['cities']),
           'cities=%d' % len(data.get('cities', [])))
    top = data.get('top', [])
    sorted_ok = all(top[i]['tickets'] >= top[i + 1]['tickets'] for i in range(len(top) - 1))
    record('T12.5', 'TOP10 按售票数降序', code == 200 and len(top) <= 10 and sorted_ok,
           'top=%d' % len(top))
    # 时间段筛选：换区间
    code2, d2 = admin.get('/admin/stats', params={'start': '2025-09-01', 'end': '2025-09-10'})
    t2 = d2.get('data', {}).get('total', {})
    record('T12.6', '时间段筛选数据变化', code2 == 200 and t2.get('orders') != total.get('orders'),
           'full=%s narrow=%s' % (total.get('orders'), t2.get('orders')))
    # 空区间
    code3, d3 = admin.get('/admin/stats', params={'start': '2030-01-01', 'end': '2030-01-02'})
    t3 = d3.get('data', {})
    record('T12.7', '空区间不报错且数据为空', code3 == 200 and d3.get('code') == 0
           and t3['total']['orders'] == 0 and t3['total']['tickets'] == 0
           and t3['daily'] == [] and t3['cats'] == [] and t3['cities'] == [] and t3['top'] == [])


# ============================================================
# T13 权限控制
# ============================================================
def t13():
    user.login('user', 'zhang_san', '123456')  # 确保用户态
    code, d = user.get('/admin/shows')
    record('T13.1a', '普通用户访问演出管理→403', code == 200 and d.get('code') == 403,
           'http=%s code=%s' % (code, d.get('code')))
    code, d = user.get('/admin/stats', params={'start': '2025-01-01', 'end': '2025-12-31'})
    record('T13.1b', '普通用户访问销售统计→403', code == 200 and d.get('code') == 403,
           'http=%s code=%s' % (code, d.get('code')))
    code, d = guest.get('/orders')
    record('T13.2a', '游客访问订单→401', code == 200 and d.get('code') == 401,
           'http=%s code=%s' % (code, d.get('code')))
    code, d = guest.get('/addresses')
    record('T13.2b', '游客访问收货信息→401', code == 200 and d.get('code') == 401,
           'http=%s code=%s' % (code, d.get('code')))
    code, d = guest.get('/attendees')
    record('T13.2c', '游客访问购票人→401', code == 200 and d.get('code') == 401,
           'http=%s code=%s' % (code, d.get('code')))


# ============================================================
# T14 数据库一致性
# ============================================================
def t14():
    conn = pymysql.connect(cursorclass=DictCursor, **DB_CONFIG)
    cur = conn.cursor()

    def q1(sql):
        cur.execute(sql)
        return cur.fetchone()

    r = q1("SELECT COUNT(*) c FROM ticket_sales.ticket_tier WHERE sold_seats>total_seats")
    record('T14.1', '不超卖', r['c'] == 0, 'oversold=%d' % r['c'])
    r = q1("""SELECT COUNT(*) c FROM (SELECT attendee_id,session_id,COUNT(*) c FROM ticket_sales.order_item
              GROUP BY attendee_id,session_id HAVING c>1) x""")
    record('T14.2', '每人每场限购1张', r['c'] == 0, 'violations=%d' % r['c'])
    r = q1("SELECT result,COUNT(*) c FROM ticket_sales.purchase_request GROUP BY result")
    cur.execute("SELECT result,COUNT(*) c FROM ticket_sales.purchase_request GROUP BY result")
    res_map = {x['result']: x['c'] for x in cur.fetchall()}
    record('T14.3', '购票请求留痕(成功+失败都有)', 1 in res_map and 0 in res_map,
           'result=%s' % res_map)
    r1 = q1("SELECT COALESCE(SUM(ticket_count),0) s FROM ticket_sales.sales_daily")
    r2 = q1("SELECT COALESCE(SUM(ticket_count),0) s FROM ticket_sales.ticket_order WHERE order_status=2")
    record('T14.4', '销售汇总一致(sales_daily=已支付订单)', r1['s'] == r2['s'],
           'daily=%s orders=%s' % (r1['s'], r2['s']))
    r = q1("""SELECT COUNT(*) c FROM ticket_sales.order_item oi
              LEFT JOIN ticket_sales.ticket_order o ON o.order_id=oi.order_id
              WHERE o.order_id IS NULL""")
    record('T14.5', '无孤儿订单明细', r['c'] == 0, 'orphans=%d' % r['c'])
    r = q1("""SELECT COUNT(*) c FROM ticket_sales.show_item
              WHERE series_id IS NULL AND show_name LIKE '%%·%%'""")
    record('T14.6', '巡演聚合完整(无未聚合的·城市站)', r['c'] == 0, 'unagg=%d' % r['c'])
    conn.close()


def main():
    print('=' * 100)
    print('自动化功能测试开始')
    print('=' * 100)
    t1()
    print('-' * 100)
    t2()
    print('-' * 100)
    t3()
    print('-' * 100)
    t4()
    print('-' * 100)
    t5()
    print('-' * 100)
    # 用户购票准备
    r1, r2, aids = setup_user()
    print('准备购票人: 甲=%s 乙=%s' % (aids, r1.get('msg') if r1 else ''))
    order_no = t6(aids)
    print('-' * 100)
    t7(aids)
    print('-' * 100)
    t8()
    print('-' * 100)
    t9()
    print('-' * 100)
    t10()
    print('-' * 100)
    t11()
    print('-' * 100)
    t12()
    print('-' * 100)
    t13()
    print('-' * 100)
    t14()
    print('=' * 100)
    print('结果汇总: 通过 %d, 失败 %d, 总计 %d' % (PASS, FAIL, PASS + FAIL))
    print('=' * 100)
    result_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'docs', 'test-results', 'test_api_results.json')
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump({'pass': PASS, 'fail': FAIL, 'results': RESULTS}, f, ensure_ascii=False, indent=1)
    print('结果已写入 docs/test-results/test_api_results.json')


if __name__ == '__main__':
    main()
