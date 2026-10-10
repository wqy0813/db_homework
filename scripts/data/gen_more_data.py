# -*- coding: utf-8 -*-
"""
批量演示数据生成器 —— 连接 ticket_sales 库，生成接近真实规模的演示数据：
  - 城市补到 35 个；
  - 新增 43 个演出、约 57 个场次、约 240 个票档；
  - 场次目标分布：45% 已结束、15% 售罄、10% 售票中、30% 预售中；
  - 300 个用户（含收货地址）；
  - 过去 90 天约 1000+ 笔已支付历史订单（周末更多）、约 2500+ 张票，
    分布在各城市/类型/日期，自动扣减余票、写订单明细（每人每场次1张）；
  - 购票请求日志（成功+失败）；
  - 重建销售日汇总 sales_daily、刷新场次售票状态。
可重复执行：每次先清理上一批批量数据（订单号以 B 开头、user_id>5、show_id>8），
           保留 seed 的 7 场核心演出与 5 个演示账号。
运行：python scripts/data/gen_more_data.py
"""
import os
import random
import sys
from datetime import datetime, timedelta, date, time

import pymysql

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))
from config import DB_CONFIG  # noqa: E402
from session_schedule import SOLD_OUT, bucket_for_index, sale_start_for, show_day_for_status  # noqa: E402

random.seed(42)

# ---------------------------------------------------------------------------
# 基础词库
# ---------------------------------------------------------------------------
NEW_CITIES = ['苏州', '青岛', '厦门', '郑州', '济南', '沈阳', '大连', '宁波', '福州',
              '合肥', '南昌', '昆明', '贵阳', '南宁', '哈尔滨', '长春', '石家庄',
              '太原', '兰州', '海口', '三亚', '无锡', '佛山']

SHOW_NAMES = [
    # 演唱会
    ('林俊杰《JJ20》世界巡回演唱会', 1), ('五月天《好好好想见到你》演唱会', 1),
    ('陈奕迅《Fear and Dreams》演唱会', 1), ('王菲《幻乐一场》演唱会', 1),
    ('薛之谦《天外来物》巡回演唱会', 1), ('邓紫棋《GLORIA》世界巡回演唱会', 1),
    ('李荣浩《纵横四海》演唱会', 1), ('华晨宇《火星》演唱会', 1),
    ('Taylor Swift 时代巡回演唱会', 1), ('刘德华《今天》巡回演唱会', 1),
    ('梁静茹《当我们谈论爱情》演唱会', 1), ('蔡依林《Ugly Beauty》演唱会', 1),
    ('毛不易《幼鸟指南》巡回演唱会', 1), ('张杰《未LIVE》巡回演唱会', 1),
    # 话剧歌剧
    ('话剧《茶馆》', 2), ('话剧《暗恋桃花源》', 2), ('话剧《白鹿原》', 2),
    ('话剧《戏台》', 2), ('音乐剧《歌剧魅影》', 2), ('音乐剧《猫》Cats', 2),
    ('话剧《威尼斯商人》', 2), ('音乐剧《巴黎圣母院》', 2),
    # 体育
    ('中超联赛 主场赛事', 3), ('CBA 职业篮球联赛', 3), ('NBA 中国赛', 3),
    ('国际乒联世界巡回赛', 3), ('羽毛球大师赛', 3), ('网球公开赛', 3),
    ('搏击争霸赛', 3),
    # 展览
    ('梵高《星夜》光影艺术展', 5), ('teamLab 无界美术馆', 5),
    ('故宫文物特展', 5), ('敦煌艺术大展', 5),
    ('恐龙化石科普展', 5), ('太空探索沉浸展', 5),
    # 音乐会
    ('维也纳皇家交响乐团新年音乐会', 6), ('久石让·宫崎骏动漫音乐会', 6),
    ('王羽佳钢琴独奏音乐会', 6), ('国家大剧院交响音乐会', 6),
    # 舞蹈芭蕾
    ('芭蕾舞剧《天鹅湖》', 7), ('芭蕾舞剧《胡桃夹子》', 7),
    ('舞剧《朱鹮》', 7), ('舞剧《永不消逝的电波》', 7),
]

# 各类型票档价位（档位名, 价格）
TIER_PRICES = {
    1: [('内场 1980', 1980), ('看台 1280', 1280), ('看台 880', 880), ('看台 580', 580), ('看台 380', 380)],
    2: [('VIP 880', 880), ('一等 580', 580), ('二等 380', 380), ('三等 180', 180)],
    3: [('特等 1280', 1280), ('一等 680', 680), ('二等 380', 380), ('三等 180', 180)],
    5: [('VIP 导览票 498', 498), ('通票 298', 298), ('平日票 198', 198), ('学生票 98', 98)],
    6: [('VIP 1280', 1280), ('一等 880', 880), ('二等 480', 480), ('三等 280', 280)],
    7: [('VIP 880', 880), ('一等 680', 680), ('二等 480', 480), ('三等 280', 280)],
}

# 各类型对应的真实海报/介绍图（本地 static/img 下的真实照片）
CAT_IMAGES = {
    1: ['/static/img/concert1.jpg', '/static/img/concert2.jpg', '/static/img/concert3.jpg'],
    2: ['/static/img/theater1.jpg', '/static/img/theater2.jpg'],
    3: ['/static/img/basket1.jpg', '/static/img/basket2.jpg'],
    5: ['/static/img/museum1.jpg', '/static/img/theater2.jpg'],
    6: ['/static/img/piano1.jpg', '/static/img/piano2.jpg'],
    7: ['/static/img/dance1.jpg', '/static/img/dance2.jpg'],
}

SURNAMES = list('王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭')
GIVEN = list('伟芳娜敏静丽强磊军洋勇艳杰娟涛明超秀兰霞平刚桂英华玉梅浩宇欣怡子涵雨桐')
STREETS = ['人民路', '解放大道', '中山路', '建设路', '和平街', '文化巷', '学府路', '滨江道',
           '迎春街', '朝阳路', '望江路', '科创街']

FAIL_REASONS = ['余票不足：该票档剩余票数不足',
                '超出限购：购票人已购买该场次门票',
                '演出尚未开售（预售中）',
                '购票人数量与票数不一致',
                '系统繁忙，请稍后重试']


def rand_name():
    return random.choice(SURNAMES) + ''.join(random.choice(GIVEN) for _ in range(random.randint(1, 2)))


def main():
    conn = pymysql.connect(autocommit=False, **DB_CONFIG)
    cur = conn.cursor()

    # ---------- 0. 清理上一批批量数据（可重复执行） ----------
    print('清理旧的批量数据 ...')
    cur.execute("DELETE oi FROM order_item oi JOIN ticket_order o ON o.order_id=oi.order_id WHERE o.order_no LIKE 'B%'")
    cur.execute("DELETE FROM ticket_order WHERE order_no LIKE 'B%'")
    cur.execute("DELETE FROM purchase_request WHERE user_id > 5")
    cur.execute("DELETE FROM attendee WHERE user_id > 5")
    cur.execute("DELETE FROM shipping_address WHERE user_id > 5")
    cur.execute("DELETE FROM app_user WHERE user_id > 5")
    cur.execute("DELETE FROM ticket_tier WHERE session_id IN (SELECT session_id FROM show_session WHERE show_id > 8)")
    cur.execute("DELETE FROM show_session WHERE show_id > 8")
    cur.execute("DELETE FROM show_image WHERE show_id > 8")
    cur.execute("DELETE FROM show_item WHERE show_id > 8")
    conn.commit()

    # ---------- 1. 城市、场馆 ----------
    print('生成城市/场馆 ...')
    cur.executemany("INSERT IGNORE INTO city(city_name) VALUES(%s)", [(c,) for c in NEW_CITIES])
    cur.execute("SELECT city_id, city_name FROM city")
    cities = [(r[0], r[1]) for r in cur.fetchall()]  # (city_id, city_name)

    venues = []
    for cid, cname in cities:
        venues.append((cid, f'{cname}市体育中心体育场', f'{cname}市体育路1号', 40000))
        venues.append((cid, f'{cname}大剧院', f'{cname}市文化广场8号', 1600))
        venues.append((cid, f'{cname}体育馆', f'{cname}市奥体大道6号', 12000))
    # 已有场馆靠 (city_id,venue_name) 唯一去重
    cur.executemany("""INSERT IGNORE INTO venue(city_id,venue_name,address,capacity)
                       VALUES(%s,%s,%s,%s)""", venues)
    cur.execute("SELECT venue_id, city_id, venue_name FROM venue")
    venue_rows = cur.fetchall()
    venues_by_city = {}
    for vid, cid, vname in venue_rows:
        venues_by_city.setdefault(cid, []).append((vid, vname))

    # ---------- 2. 批量用户 + 收货地址 ----------
    print('生成用户 ...')
    N_USER = 300
    users = []
    for i in range(N_USER):
        uname = 'u%06d' % (i + 1)
        phone = '139%08d' % (10000000 + i)
        users.append((uname, '$2b$10$0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ',
                      phone, f'{uname}@example.com', 1))
    cur.executemany("""INSERT INTO app_user(username,password_hash,phone,email,status)
                       VALUES(%s,%s,%s,%s,%s)""", users)
    cur.execute("SELECT user_id, username FROM app_user WHERE username LIKE 'u%'")
    bulk_users = [r[0] for r in cur.fetchall()]

    addrs = []
    for uid in bulk_users:
        nm = rand_name()
        cid, cname = random.choice(cities)
        addrs.append((uid, nm, '13%09d' % random.randint(0, 999999999),
                      f'{cname}市{random.choice(STREETS)}{random.randint(1,200)}号',
                      1 if random.random() < 0.6 else 0))
    cur.executemany("""INSERT INTO shipping_address(user_id,receiver_name,phone,address_detail,is_default)
                       VALUES(%s,%s,%s,%s,%s)""", addrs)
    cur.execute("SELECT address_id, user_id FROM shipping_address WHERE user_id > 5")
    addr_of_user = {}
    for aid, uid in cur.fetchall():
        addr_of_user[uid] = aid

    # ---------- 3. 演出 / 场次 / 票档 ----------
    print('生成演出/场次/票档 ...')
    today = date.today()
    tiers = []  # 内存票档：dict 列表
    sold_out_sessions = set()
    session_counts = [random.choice([1, 1, 2]) for _ in SHOW_NAMES]
    total_sessions = sum(session_counts)
    session_index = 0
    for seq, (name, cat) in enumerate(SHOW_NAMES):
        cid, cname = random.choice(cities)
        vlist = venues_by_city.get(cid) or random.choice(list(venues_by_city.values()))
        imgs = CAT_IMAGES[cat]
        poster = imgs[0]
        cur.execute("""INSERT INTO show_item(show_name,category_id,city_id,poster_url,description,admin_id)
                       VALUES(%s,%s,%s,%s,%s,1)""",
                    (name, cat, cid, poster, f'{name}，精彩呈现，欢迎购票。'))
        show_id = cur.lastrowid
        # 介绍图片 2-3 张（从本类型真实图片中循环取）
        for k in range(1, random.randint(2, 4)):
            cur.execute("INSERT INTO show_image(show_id,image_url,sort_no) VALUES(%s,%s,%s)",
                        (show_id, imgs[k % len(imgs)], k))
        # 每场演出生成 1-2 个同状态场次；销售时间统一提前 30 天。
        n_sess = session_counts[seq]
        used_slots = set()
        for s in range(n_sess):
            status = bucket_for_index(session_index, total_sessions)
            vid, vname = random.choice(vlist)
            while True:
                show_day = show_day_for_status(status, today, random)
                hh, mm = random.choice([(19, 30), (20, 0), (14, 30), (19, 0)])
                slot = (show_day, hh, mm)
                if slot not in used_slots:
                    used_slots.add(slot)
                    break
            show_dt = datetime.combine(show_day, time(hh, mm))
            sale_dt = sale_start_for(show_dt)
            cur.execute("""INSERT INTO show_session(show_id,venue_id,show_time,sale_start,sale_status)
                           VALUES(%s,%s,%s,%s,%s)""", (show_id, vid, show_dt, sale_dt, status))
            session_id = cur.lastrowid
            if status == SOLD_OUT:
                sold_out_sessions.add(session_id)
            # 票档 3-5 个
            price_tiers = TIER_PRICES[cat]
            for tname, price in price_tiers:
                total = random.choice([300, 500, 800, 1200, 2000, 3000])
                cur.execute("""INSERT INTO ticket_tier(session_id,tier_name,price,total_seats,sold_seats)
                               VALUES(%s,%s,%s,%s,0)""", (session_id, tname, price, total))
                tiers.append({'tier_id': cur.lastrowid, 'session_id': session_id,
                              'price': float(price), 'total': total, 'sold': 0,
                              'sale_start': sale_dt, 'show_time': show_dt})
            session_index += 1
    conn.commit()

    # 把 seed 票档也纳入内存（用于售出）
    cur.execute("""SELECT t.tier_id, t.session_id, t.price, t.total_seats, t.sold_seats,
                          se.sale_start, se.show_time
                   FROM ticket_tier t JOIN show_session se ON se.session_id=t.session_id""")
    tier_mem = {}
    for tid, sid, price, total, sold, sale_start, show_time in cur.fetchall():
        tier_mem[tid] = {'tier_id': tid, 'session_id': sid, 'price': float(price),
                         'total': total, 'sold': sold, 'sale_start': sale_start, 'show_time': show_time}
    for t in tiers:
        tier_mem[t['tier_id']] = t

    # ---------- 4. 历史订单（过去 90 天） ----------
    print('生成历史订单 ...')
    orders, items, attendees, reqs = [], [], [], []
    daily = {}  # date -> [orders, tickets, amount]
    order_seq = 0
    att_seq = 0

    for day_off in range(90, 0, -1):
        d = today - timedelta(days=day_off)
        is_weekend = d.weekday() >= 5
        n_orders = random.randint(12, 26) if is_weekend else random.randint(4, 13)
        for _ in range(n_orders):
            # 选当时可售（已开售、未开演、有余票）的票档
            cand = [t for t in tier_mem.values()
                    if t['sale_start'] <= datetime.combine(d, time(12)) < t['show_time']
                    and t['total'] - t['sold'] > 0]
            if not cand:
                continue
            t = random.choice(cand)
            k = random.choice([1, 1, 1, 2, 2, 3])
            remain = t['total'] - t['sold']
            if remain < k:
                k = remain
            if k <= 0:
                continue
            uid = random.choice(bulk_users)
            addr_id = addr_of_user[uid]
            pay_dt = datetime.combine(d, time(random.randint(9, 22), random.randint(0, 59)))
            order_seq += 1
            order_no = 'B%s%05d' % (d.strftime('%Y%m%d'), order_seq)
            amount = t['price'] * k
            orders.append((order_no, uid, t['session_id'], t['tier_id'], addr_id,
                           k, amount, 2, pay_dt, pay_dt))
            # 每张票新建一位购票人（保证不撞限购唯一键）
            for _i in range(k):
                att_seq += 1
                aname = rand_name()
                idno = 'B%08d' % att_seq
                cur.execute("INSERT INTO attendee(user_id,attendee_name,id_type,id_no) VALUES(%s,%s,1,%s)",
                            (uid, aname, idno))
                att_id = cur.lastrowid
                items.append((order_seq, t['tier_id'], att_id, t['session_id'], t['price']))
            t['sold'] += k
            reqs.append((uid, t['session_id'], t['tier_id'], k, 1, None, pay_dt))
            dd = daily.setdefault(d, [0, 0, 0.0])
            dd[0] += 1; dd[1] += k; dd[2] += amount
        # 少量失败请求
        for _ in range(random.randint(0, 2)):
            t = random.choice(list(tier_mem.values()))
            uid = random.choice(bulk_users)
            rt = datetime.combine(d, time(random.randint(9, 22), random.randint(0, 59)))
            reqs.append((uid, t['session_id'], t['tier_id'], random.randint(1, 3),
                         0, random.choice(FAIL_REASONS), rt))

    # 订单先插入拿到真实 order_id（order_no 唯一，用它回填明细）
    print('  写入 %d 笔订单、%d 张票 ...' % (len(orders), len(items)))
    cur.executemany("""INSERT INTO ticket_order(order_no,user_id,session_id,tier_id,address_id,
                          ticket_count,total_amount,order_status,create_time,pay_time)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", orders)
    # 建立 order_no -> order_id 映射（items 顺序与 orders 一一对应：每订单 k 行）
    cur.execute("SELECT order_id, order_no FROM ticket_order WHERE order_no LIKE 'B%'")
    oid_of_no = {no: oid for oid, no in cur.fetchall()}
    final_items = []
    it_idx = 0
    for o in orders:
        order_no = o[0]; k = o[5]
        oid = oid_of_no[order_no]
        for _j in range(k):
            _, tier_id, att_id, sid, price = items[it_idx]
            final_items.append((oid, tier_id, att_id, sid, price))
            it_idx += 1
    cur.executemany("""INSERT INTO order_item(order_id,tier_id,attendee_id,session_id,unit_price)
                       VALUES(%s,%s,%s,%s,%s)""", final_items)
    cur.executemany("""INSERT INTO purchase_request(user_id,session_id,tier_id,ticket_count,result,fail_reason,request_time)
                       VALUES(%s,%s,%s,%s,%s,%s,%s)""", reqs)

    # ---------- 5. 回写票档已售、重建销售汇总、刷新场次状态 ----------
    print('回写余票 / 汇总 / 状态 ...')
    for tier in tier_mem.values():
        if tier['session_id'] in sold_out_sessions:
            tier['sold'] = tier['total']
    cur.executemany("UPDATE ticket_tier SET sold_seats=%s WHERE tier_id=%s",
                    [(t['sold'], tid) for tid, t in tier_mem.items()])
    cur.execute("TRUNCATE TABLE sales_daily")
    cur.execute("""INSERT INTO sales_daily(stat_date,order_count,ticket_count,total_amount)
                   SELECT DATE(pay_time), COUNT(*), SUM(ticket_count), SUM(total_amount)
                   FROM ticket_order WHERE order_status=2 AND pay_time IS NOT NULL
                   GROUP BY DATE(pay_time)""")
    # Past sessions are closed; a future session with no inventory is sold out.
    cur.execute("UPDATE show_session SET sale_status=4 WHERE show_time<=NOW()")
    cur.execute("""UPDATE show_session se SET se.sale_status=3
                   WHERE se.show_time>NOW()
                     AND EXISTS (SELECT 1 FROM ticket_tier t WHERE t.session_id=se.session_id)
                     AND NOT EXISTS (SELECT 1 FROM ticket_tier t
                                     WHERE t.session_id=se.session_id AND t.total_seats-t.sold_seats>0)""")
    conn.commit()

    # ---------- 6. 统计输出 ----------
    def cnt(sql):
        cur.execute(sql); return cur.fetchone()[0]
    print('----------------------------------------')
    print('生成完成！当前数据量：')
    print('  演出 show_item      :', cnt("SELECT COUNT(*) FROM show_item"))
    print('  场次 show_session    :', cnt("SELECT COUNT(*) FROM show_session"))
    print('  票档 ticket_tier     :', cnt("SELECT COUNT(*) FROM ticket_tier"))
    print('  用户 app_user        :', cnt("SELECT COUNT(*) FROM app_user"))
    print('  订单 ticket_order    :', cnt("SELECT COUNT(*) FROM ticket_order"))
    print('  票 order_item        :', cnt("SELECT COUNT(*) FROM order_item"))
    print('  购票请求 purchase_req :', cnt("SELECT COUNT(*) FROM purchase_request"))
    print('  场次状态分布:')
    cur.execute("SELECT sale_status, COUNT(*) AS c FROM show_session GROUP BY sale_status ORDER BY sale_status")
    for status, count in cur.fetchall():
        print('    %s: %s' % (status, count))
    cur.execute("SELECT COALESCE(SUM(total_amount),0), COALESCE(SUM(ticket_count),0) FROM ticket_order WHERE order_status=2")
    amt, tk = cur.fetchone()
    print('  累计售票 %s 张，销售额 ¥%.2f' % (tk, float(amt)))
    conn.close()


if __name__ == '__main__':
    main()
