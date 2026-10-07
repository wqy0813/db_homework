# -*- coding: utf-8 -*-
"""
满规模压测数据生成器 —— 按题目给定数据量灌入接近目标的数据：
  - 城市 100+ 个；
  - 用户 10 万（f000001..f100000，每人一个收货地址）；
  - 约 1000 个演出场次、~400 个演出项目、每场 4 档票、场均 5000 座；
  - 场次状态目标分布：45% 已结束、15% 售罄、10% 售票中、30% 预售中；
  - 过去 365 天约 100 万张已售票（~40 万订单、100 万购票人），
    周末销量更高，自动维护余票/限购/金额/sales_daily。
可重复执行（按标记清理：f% 用户、F% 订单、poster '/img/full/' 演出）。
运行：python scripts/data/gen_full_scale.py
"""
import os
import random
import sys
import time
from datetime import datetime, timedelta, date, time as dtime

import pymysql

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))
from config import DB_CONFIG  # noqa: E402
from session_schedule import SOLD_OUT, bucket_for_index, sale_start_for, show_day_for_status  # noqa: E402

random.seed(7)

TARGET_SESSIONS = 1000
TARGET_TICKETS = 1_000_000
BATCH = 4000          # 每批 flush 的票数
USER_TOTAL = 100_000

# 新增城市（在已有 35 城基础上再补 65 个规范城市名，合计 100）
MORE_CITIES = [
    '东莞', '泉州', '温州', '绍兴', '嘉兴', '台州', '金华', '徐州', '常州', '扬州',
    '南通', '镇江', '烟台', '潍坊', '临沂', '淄博', '洛阳', '开封', '宜昌', '襄阳',
    '衡阳', '株洲', '岳阳', '桂林', '柳州', '遵义', '绵阳', '德阳', '南充', '宜宾',
    '泸州', '曲靖', '赣州', '九江', '上饶', '芜湖', '蚌埠', '马鞍山', '邯郸', '保定',
    '唐山', '秦皇岛', '呼和浩特', '包头', '乌鲁木齐', '银川', '西宁', '拉萨', '鞍山',
    '抚顺', '大庆', '齐齐哈尔', '锦州', '咸阳', '宝鸡', '大同', '临汾', '吉林',
    '张家口', '承德', '沧州', '廊坊', '衡水', '邢台', '阳泉',
]

IPS = {
    1: ['周杰伦', '五月天', '陈奕迅', '林俊杰', '邓紫棋', '薛之谦', '李荣浩', '华晨宇',
        '张杰', '毛不易', '刘德华', '王菲', '蔡依林', '梁静茹', '张学友', '谢霆锋',
        '王力宏', '陶喆', '周深', '李宇春', '张靓颖', '萧敬腾', '方大同', '吴青峰',
        '时代少年团', '黎明', '郭富城', '周笔畅', '刘宇宁', '谭咏麟'],
    2: ['茶馆', '雷雨', '暗恋桃花源', '白鹿原', '戏台', '窝头会馆', '大宅门',
        '甄嬛传话剧', '如梦之梦', '宝岛一村', '歌剧魅影', '猫', '巴黎圣母院', '西贡小姐'],
    3: ['中超联赛', 'CBA篮球联赛', 'NBA中国赛', '乒联世界巡回赛', '羽毛球大师赛',
        '网球公开赛', '搏击争霸赛', '城市马拉松', '电竞大赛', '排球超级联赛'],
    4: ['小猪佩奇', '奥特曼', '熊出没', '汪汪队立大功', '冰雪奇缘', '超级飞侠',
        '海底小纵队', '喜羊羊', '大头儿子', '变形金刚'],
    5: ['梵高光影展', '莫奈沉浸展', '毕加索真迹展', '达利艺术展', 'teamLab无界',
        '故宫文物特展', '敦煌艺术大展', '恐龙化石展', '太空探索展', '古埃及文明展'],
    6: ['久石让音乐会', '郎朗钢琴', '王羽佳钢琴', '维也纳交响', '柏林爱乐',
        '国家大剧院交响', '中国爱乐', '马克西姆钢琴', '理查德钢琴', '李云迪钢琴'],
    7: ['天鹅湖', '胡桃夹子', '朱鹮', '只此青绿', '永不消逝的电波', '睡美人',
        '吉赛尔', '红楼梦舞剧', '孔子舞剧', '舞俑'],
}

# 每场 4 档票，合计 5000 座
TIERS = {
    1: [('内场 1280', 1280, 800), ('看台 880', 880, 1500), ('看台 580', 580, 1700), ('看台 380', 380, 1000)],
    2: [('VIP 880', 880, 500), ('一等 580', 580, 1000), ('二等 380', 380, 1500), ('三等 180', 180, 2000)],
    3: [('特等 1280', 1280, 1000), ('一等 680', 680, 1500), ('二等 380', 380, 1500), ('三等 180', 180, 1000)],
    4: [('套票 480', 480, 1000), ('一等 380', 380, 1500), ('二等 280', 280, 1500), ('三等 180', 180, 1000)],
    5: [('VIP 498', 498, 500), ('通票 298', 298, 1500), ('平日 198', 198, 2000), ('学生票 98', 98, 1000)],
    6: [('VIP 1280', 1280, 500), ('一等 880', 880, 1000), ('二等 480', 480, 1500), ('三等 280', 280, 2000)],
    7: [('VIP 880', 880, 500), ('一等 680', 680, 1000), ('二等 480', 480, 1500), ('三等 280', 280, 2000)],
}

SURNAMES = list('王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾萧田董袁潘蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤')


def rname():
    return random.choice(SURNAMES) + ''.join(random.choice('伟芳娜敏静丽强磊军洋勇艳杰娟涛明超秀兰霞平桂英华玉梅浩宇欣怡子涵雨桐嘉怡梓萱浩然宇航') for _ in range(random.randint(1, 2)))


def main():
    t0 = time.time()
    conn = pymysql.connect(autocommit=False, **DB_CONFIG)
    cur = conn.cursor()

    print('[1/5] 清理旧满规模数据 ...')
    cur.execute("SELECT venue_id FROM venue WHERE venue_name LIKE '%（满规模）%'")
    cur.execute("DELETE oi FROM order_item oi JOIN ticket_order o ON o.order_id=oi.order_id WHERE o.order_no LIKE 'F%'")
    cur.execute("DELETE FROM ticket_order WHERE order_no LIKE 'F%'")
    cur.execute("DELETE FROM purchase_request WHERE user_id IN (SELECT user_id FROM app_user WHERE username LIKE 'f%')")
    cur.execute("DELETE FROM attendee WHERE user_id IN (SELECT user_id FROM app_user WHERE username LIKE 'f%')")
    cur.execute("DELETE FROM shipping_address WHERE user_id IN (SELECT user_id FROM app_user WHERE username LIKE 'f%')")
    cur.execute("DELETE FROM app_user WHERE username LIKE 'f%'")
    cur.execute("DELETE FROM ticket_tier WHERE session_id IN (SELECT session_id FROM show_session WHERE show_id IN (SELECT show_id FROM show_item WHERE poster_url LIKE '/img/full/%'))")
    cur.execute("DELETE FROM show_session WHERE show_id IN (SELECT show_id FROM show_item WHERE poster_url LIKE '/img/full/%')")
    cur.execute("DELETE FROM show_image WHERE show_id IN (SELECT show_id FROM show_item WHERE poster_url LIKE '/img/full/%')")
    cur.execute("DELETE FROM show_item WHERE poster_url LIKE '/img/full/%'")
    cur.execute("DELETE FROM venue WHERE venue_name LIKE '%（满规模）%'")
    conn.commit()

    print('[2/5] 城市 / 场馆 ...')
    cur.executemany("INSERT IGNORE INTO city(city_name) VALUES(%s)", [(c,) for c in MORE_CITIES])
    cur.execute("SELECT city_id, city_name FROM city")
    cities = [(r[0], r[1]) for r in cur.fetchall()]
    print('      城市总数 =', len(cities))
    # 每城一个满规模场馆（5000+ 座）
    cur.executemany("""INSERT IGNORE INTO venue(city_id,venue_name,address,capacity)
                       VALUES(%s,%s,%s,%s)""",
                    [(cid, f'{cname}国际演艺中心（满规模）', f'{cname}满规模大道1号', 6000) for cid, cname in cities])
    cur.execute("SELECT venue_id, city_id FROM venue WHERE venue_name LIKE '%（满规模）%'")
    venue_of_city = {cid: vid for vid, cid in cur.fetchall()}

    print('[3/5] 10 万用户 ...')
    user_rows = [(f'f{i:06d}', '$2b$10$0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ',
                  f'136{i:08d}', f'f{i:06d}@example.com', 1)
                 for i in range(1, USER_TOTAL + 1)]
    for k in range(0, len(user_rows), 5000):
        cur.executemany("""INSERT INTO app_user(username,password_hash,phone,email,status)
                           VALUES(%s,%s,%s,%s,%s)""", user_rows[k:k + 5000])
    conn.commit()
    cur.execute("SELECT user_id FROM app_user WHERE username LIKE 'f%'")
    fusers = [r[0] for r in cur.fetchall()]
    print('      用户数 =', len(fusers))
    # 收货地址
    addr_rows = [(uid, rname(), f'13{random.randint(0,999999999):09d}',
                  f'{random.choice(cities)[1]}市测试路{random.randint(1,999)}号', 1) for uid in fusers]
    for k in range(0, len(addr_rows), 5000):
        cur.executemany("""INSERT INTO shipping_address(user_id,receiver_name,phone,address_detail,is_default)
                           VALUES(%s,%s,%s,%s,%s)""", addr_rows[k:k + 5000])
    conn.commit()
    cur.execute("SELECT user_id, address_id FROM shipping_address WHERE user_id IN (SELECT user_id FROM app_user WHERE username LIKE 'f%')")
    addr_of = {uid: aid for uid, aid in cur.fetchall()}

    print('[4/5] 演出 / 场次 / 票档（约 %d 场次）...' % TARGET_SESSIONS)
    today = date.today()
    show_cache = {}          # (ip, city_id) -> show_id
    tiers_mem = []           # 票档内存
    sold_out_sessions = set()
    sess_cnt = 0
    while sess_cnt < TARGET_SESSIONS:
        cat = random.choices([1, 2, 3, 4, 5, 6, 7], weights=[4, 2, 2, 2, 2, 1, 1])[0]
        ip = random.choice(IPS[cat])
        cid, cname = random.choice(cities)
        key = (ip, cid)
        if key not in show_cache:
            cur.execute("""INSERT INTO show_item(show_name,category_id,city_id,poster_url,description,admin_id)
                           VALUES(%s,%s,%s,%s,%s,1)""",
                        (f'{ip}·{cname}站', cat, cid, '/img/full/p.jpg', f'{ip}{cname}站，满规模压测演出。'))
            sid = cur.lastrowid
            cur.executemany("INSERT INTO show_image(show_id,image_url,sort_no) VALUES(%s,%s,%s)",
                            [(sid, f'/img/full/{sid}_{k}.jpg', k) for k in (1, 2)])
            show_cache[key] = sid
            show_sess_count = 0
        sid = show_cache[key]
        # 每个演出最多 3 场
        cur.execute("SELECT COUNT(*) FROM show_session WHERE show_id=%s", (sid,))
        if cur.fetchone()[0] >= 3:
            continue
        vid = venue_of_city[cid]
        status = bucket_for_index(sess_cnt, TARGET_SESSIONS)
        show_day = show_day_for_status(status, today, random)
        show_dt = datetime.combine(show_day, dtime(19, 30))
        sale_dt = sale_start_for(show_dt)
        cur.execute("""INSERT INTO show_session(show_id,venue_id,show_time,sale_start,sale_status)
                       VALUES(%s,%s,%s,%s,%s)""", (sid, vid, show_dt, sale_dt, status))
        seid = cur.lastrowid
        if status == SOLD_OUT:
            sold_out_sessions.add(seid)
        for tname, price, total in TIERS[cat]:
            cur.execute("""INSERT INTO ticket_tier(session_id,tier_name,price,total_seats,sold_seats)
                           VALUES(%s,%s,%s,%s,0)""", (seid, tname, price, total))
            tiers_mem.append({'tid': cur.lastrowid, 'sid': seid, 'price': float(price),
                              'total': total, 'sold': 0, 'sale': sale_dt, 'show': show_dt})
        sess_cnt += 1
    conn.commit()
    print('      演出项目 =', len(show_cache), ' 票档 =', len(tiers_mem))

    print('[5/5] 历史订单（目标 %d 张票）...' % TARGET_TICKETS)
    tickets_done = 0
    orders_batch, att_batch, req_batch = [], [], []
    att_counter = 0
    order_counter = 0

    def flush():
        if not orders_batch:
            return
        # 购票人（每张票一位）；用 MAX(id) 回查本批真实自增 ID，避免 lastrowid 推算误差
        cur.execute("SELECT COALESCE(MAX(attendee_id),0) FROM attendee"); att_base = cur.fetchone()[0]
        cur.executemany("INSERT INTO attendee(user_id,attendee_name,id_type,id_no) VALUES(%s,%s,1,%s)",
                        att_batch)
        cur.execute("SELECT attendee_id FROM attendee WHERE attendee_id>%s ORDER BY attendee_id", (att_base,))
        att_ids = [r[0] for r in cur.fetchall()]
        # 订单
        cur.execute("SELECT COALESCE(MAX(order_id),0) FROM ticket_order"); ord_base = cur.fetchone()[0]
        cur.executemany("""INSERT INTO ticket_order(order_no,user_id,session_id,tier_id,address_id,
                                ticket_count,total_amount,order_status,create_time,pay_time)
                           VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", orders_batch)
        cur.execute("SELECT order_id FROM ticket_order WHERE order_id>%s ORDER BY order_id", (ord_base,))
        ord_ids = [r[0] for r in cur.fetchall()]
        # 明细：按订单顺序，每订单 k 张；购票人按本批插入顺序一一对应
        rows, ai = [], 0
        for oi, od in enumerate(orders_batch):
            _ono, _uid, sid, tid, _addr, k, amt, _st, _ct, _pt = od
            unit = amt / k
            for _ in range(k):
                rows.append((ord_ids[oi], tid, att_ids[ai], sid, unit)); ai += 1
        cur.executemany("""INSERT INTO order_item(order_id,tier_id,attendee_id,session_id,unit_price)
                           VALUES(%s,%s,%s,%s,%s)""", rows)
        cur.executemany("""INSERT INTO purchase_request(user_id,session_id,tier_id,ticket_count,result,fail_reason,request_time)
                           VALUES(%s,%s,%s,%s,%s,%s,%s)""", req_batch)
        conn.commit()
        orders_batch.clear(); att_batch.clear(); req_batch.clear()

    for day_off in range(365, 0, -1):
        if tickets_done >= TARGET_TICKETS:
            break
        d = today - timedelta(days=day_off)
        d12 = datetime.combine(d, dtime(12))
        weight = 1.8 if d.weekday() >= 5 else 1.0
        day_target = int(TARGET_TICKETS / 365 * weight * random.uniform(0.7, 1.3))
        # 当天在售（已开售、未开演）的票档，每天计算一次；售罄的会在下方跳过
        cand = [t for t in tiers_mem if t['sale'] <= d12 < t['show']]
        if not cand:
            continue
        made = 0
        attempts = 0
        while made < day_target and tickets_done < TARGET_TICKETS and attempts < day_target * 8:
            attempts += 1
            t = random.choice(cand)   # 允许同一票档当天被多次选中
            k = random.choice([1, 2, 2, 3, 4])
            if t['total'] - t['sold'] < k:
                continue
            uid = random.choice(fusers)
            pay = datetime.combine(d, dtime(random.randint(9, 22), random.randint(0, 59)))
            order_counter += 1
            ono = 'F%04d%06d' % (d.year % 100, order_counter)
            amt = t['price'] * k
            od = (ono, uid, t['sid'], t['tid'], addr_of[uid], k, amt, 2, pay, pay)
            orders_batch.append(od)
            for _ in range(k):
                att_counter += 1
                att_batch.append((uid, rname(), 'FA%08d' % att_counter))
            req_batch.append((uid, t['sid'], t['tid'], k, 1, None, pay))
            t['sold'] += k; made += k; tickets_done += k
            if len(orders_batch) >= 800:
                flush()
    flush()

    print('      回写余票 / 汇总 / 状态 ...')
    for tier in tiers_mem:
        if tier['sid'] in sold_out_sessions:
            tier['sold'] = tier['total']
    cur.executemany("UPDATE ticket_tier SET sold_seats=%s WHERE tier_id=%s",
                    [(t['sold'], t['tid']) for t in tiers_mem])
    # 销售汇总按全部已支付订单权威重建（TRUNCATE 保证重复执行不重复累加）
    cur.execute("TRUNCATE TABLE sales_daily")
    cur.execute("""INSERT INTO sales_daily(stat_date,order_count,ticket_count,total_amount)
                   SELECT DATE(pay_time), COUNT(*), SUM(ticket_count), SUM(total_amount)
                   FROM ticket_order WHERE order_status=2 AND pay_time IS NOT NULL
                   GROUP BY DATE(pay_time)""")
    cur.execute("UPDATE show_session SET sale_status=4 WHERE show_time<=NOW()")
    cur.execute("""UPDATE show_session se SET se.sale_status=3
                   WHERE se.show_time>NOW()
                     AND EXISTS (SELECT 1 FROM ticket_tier t WHERE t.session_id=se.session_id)
                     AND NOT EXISTS (SELECT 1 FROM ticket_tier t WHERE t.session_id=se.session_id AND t.total_seats-t.sold_seats>0)""")
    conn.commit()

    def cnt(sql):
        cur.execute(sql); return cur.fetchone()[0]
    print('----------------------------------------')
    print('满规模数据生成完成，用时 %.1f 分钟' % ((time.time() - t0) / 60))
    print('  城市            :', cnt("SELECT COUNT(*) FROM city"))
    print('  用户            :', cnt("SELECT COUNT(*) FROM app_user"))
    print('  演出项目        :', cnt("SELECT COUNT(*) FROM show_item"))
    print('  场次            :', cnt("SELECT COUNT(*) FROM show_session"))
    print('  票档            :', cnt("SELECT COUNT(*) FROM ticket_tier"))
    print('  订单            :', cnt("SELECT COUNT(*) FROM ticket_order"))
    print('  票(明细)        :', cnt("SELECT COUNT(*) FROM order_item"))
    cur.execute("SELECT COALESCE(SUM(ticket_count),0) FROM ticket_order WHERE order_status=2")
    print('  已售票数        :', cur.fetchone()[0])
    print('  超卖票档        :', cnt("SELECT COUNT(*) FROM ticket_tier WHERE sold_seats>total_seats"))
    conn.close()


if __name__ == '__main__':
    main()
