# -*- coding: utf-8 -*-
"""数据规范化迁移（第 4 期收尾）：
  1) 演唱会按【艺人】聚合为一个 series，series 名 = "XX 巡回演唱会"（不含歌名/主题名）
  2) 删除儿童亲子剧类（大麦几乎没有）：含订单、演出、场次、票档、series
  3) 体育只删除中超/NBA/乒联（保留 CBA、羽毛球、网球、搏击等）；CBA 系列合并为一个
  用法：
    python scripts/data/normalize_data.py --dry    # 只统计，不修改
    python scripts/data/normalize_data.py          # 真执行（删除前自动备份到 sql/backups/）
"""
import os
import sys
import time
import shutil
import pymysql

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))
from config import DB_CONFIG  # noqa: E402

DRY = '--dry' in sys.argv

# 要删除的体育关键词（只删中超/NBA/乒联；羽毛球/网球/搏击/马拉松等保留）
SPORT_DROP_KW = ['中超', 'NBA', '乒联']
# 演唱会歌手列表（规范化后每个歌手一个 series，名字 = 歌手 + 巡回演唱会）
CONCERT_ARTISTS = [
    '五月天', '刘宇宁', '刘德华', '华晨宇', '吴青峰', '周杰伦', '周深', '周笔畅', '张学友',
    '张杰', '张靓颖', '方大同', '时代少年团', '李宇春', '李荣浩', '林俊杰', '梁静茹', '毛不易',
    '王力宏', '王菲', '萧敬腾', '蔡依林', '薛之谦', '谢霆锋', '谭咏麟', '邓紫棋', '郭富城',
    '陈奕迅', '陶喆', '黎明', 'Taylor Swift',
]


def main():
    conn = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, autocommit=False, **DB_CONFIG)
    cur = conn.cursor()

    # ---------- 统计阶段（dry 和执行前都跑一遍展示） ----------
    cur.execute("SELECT show_id FROM show_item WHERE category_id=4")
    kids_shows = [r['show_id'] for r in cur.fetchall()]
    cur.execute("SELECT show_id, show_name FROM show_item WHERE category_id=3")
    sport_shows = cur.fetchall()
    sport_drop = [r['show_id'] for r in sport_shows if any(k in r['show_name'] for k in SPORT_DROP_KW)]
    cur.execute("""SELECT show_id, show_name, series_id FROM show_item
                   WHERE (category_id=3 AND show_name LIKE '%CBA%') OR show_name LIKE '%篮球%'""")
    cba_shows = cur.fetchall()

    print('=' * 60)
    print('【预演/统计】' if DRY else '【执行】')
    print('=' * 60)
    print('① 儿童亲子剧类：删除演出 %d 场' % len(kids_shows))
    cur.execute("SELECT COUNT(*) c FROM ticket_order o JOIN show_session se ON se.session_id=o.session_id "
                "JOIN show_item s ON s.show_id=se.show_id WHERE s.category_id=4")
    print('   关联订单 %d 笔' % cur.fetchone()['c'])
    cur.execute("SELECT COUNT(*) c FROM show_series WHERE category_id=4")
    print('   删除 series %d 个' % cur.fetchone()['c'])
    print('② 体育删除（中超/NBA/乒联）：演出 %d 场' % len(sport_drop))
    if sport_drop:
        ph = ','.join(['%s'] * len(sport_drop))
        cur.execute("SELECT COUNT(*) c FROM ticket_order o JOIN show_session se ON se.session_id=o.session_id "
                    "JOIN show_item s ON s.show_id=se.show_id WHERE s.show_id IN (%s)" % ph, sport_drop)
        print('   关联订单 %d 笔' % cur.fetchone()['c'])
    print('   CBA 相关演出 %d 场并入一个 "CBA 职业篮球联赛" 巡演' % len(cba_shows))
    print('③ 演唱会歌手聚合：按 %d 位歌手各建 "XX 巡回演唱会" series' % len(CONCERT_ARTISTS))
    conn.rollback()

    if DRY:
        print()
        print('DRY 模式：以上为将要执行的改动。确认无误后运行：python scripts/data/normalize_data.py')
        conn.close()
        return

    # ---------- 执行阶段 ----------
    print()
    print('执行中...')
    # 0) 备份：用 mysqldump（快，且一致性保证）；只备份会被影响的表 + 小字典
    bak_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'sql', 'backups')
    os.makedirs(bak_dir, exist_ok=True)
    bak = os.path.join(bak_dir, 'backup_%s.sql' % time.strftime('%Y%m%d_%H%M%S'))
    import subprocess
    mysqldump = os.environ.get('MYSQLDUMP') or shutil.which('mysqldump')
    if not mysqldump:
        mysql_bin = os.environ.get('MYSQL_BIN')
        if mysql_bin:
            candidate = os.path.join(mysql_bin, 'mysqldump.exe')
            if os.path.exists(candidate):
                mysqldump = candidate
    if mysqldump:
        # 备份全部表（含数据），单文件；用 --single-transaction 一致性
        cmd = [mysqldump, '-h', DB_CONFIG['host'], '-P', str(DB_CONFIG['port']),
               '-u', DB_CONFIG['user']]
        if DB_CONFIG.get('password'):
            cmd.append('-p%s' % DB_CONFIG['password'])
        cmd += [
               '--single-transaction', '--default-character-set=utf8mb4',
               '--databases', DB_CONFIG['database'], '--result-file=%s' % bak]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            print('备份警告:', r.stderr[:300])
        else:
            print('已备份 -> %s (%d KB)' % (bak, os.path.getsize(bak) // 1024))
    else:
        print('未找到 mysqldump，跳过备份')
    conn.commit()

    # 1) 删儿童剧订单（通过 show 下的 session 关联，分批提交避免大事务）
    def delete_orders_for_shows(show_ids, label, batch=5000):
        if not show_ids:
            return 0
        ph = ','.join(['%s'] * len(show_ids))
        cur.execute("SELECT o.order_id FROM ticket_order o JOIN show_session se ON se.session_id=o.session_id "
                    "WHERE se.show_id IN (%s)" % ph, show_ids)
        oids = [r['order_id'] for r in cur.fetchall()]
        if not oids:
            return 0
        total = len(oids)
        # 分批删除 order_item + order（每批独立 commit）
        for i in range(0, total, batch):
            chunk = oids[i:i + batch]
            oph = ','.join(['%s'] * len(chunk))
            cur.execute("DELETE FROM order_item WHERE order_id IN (%s)" % oph, chunk)
            cur.execute("DELETE FROM ticket_order WHERE order_id IN (%s)" % oph, chunk)
            conn.commit()
        # purchase_request 按 session 删（一批）
        cur.execute("DELETE FROM purchase_request WHERE session_id IN "
                    "(SELECT session_id FROM show_session WHERE show_id IN (%s))" % ph, show_ids)
        conn.commit()
        # 注意：购票人 attendee 保留（可能被其他订单引用，避免外键风险；不影响功能）
        print('   %s：已删订单 %d 笔' % (label, total))
        return total

    n1 = delete_orders_for_shows(kids_shows, '儿童剧')
    print('① 删除儿童剧订单:', n1, '笔')

    # 2) 删儿童剧演出（级联 session/tier/image）与 series
    if kids_shows:
        kph = ','.join(['%s'] * len(kids_shows))
        cur.execute("DELETE FROM show_item WHERE show_id IN (%s)" % kph, kids_shows)
    cur.execute("DELETE FROM show_series WHERE category_id=4")
    conn.commit()
    print('① 儿童剧演出与 series 已删除')

    # 3) 删体育（中超/NBA/乒联）
    n2 = delete_orders_for_shows(sport_drop, '体育')
    print('② 删除体育(中超/NBA/乒联)订单:', n2, '笔')
    if sport_drop:
        sph = ','.join(['%s'] * len(sport_drop))
        cur.execute("DELETE FROM show_item WHERE show_id IN (%s)" % sph, sport_drop)
    cur.execute("DELETE FROM show_series WHERE series_name LIKE '%中超%' OR series_name LIKE '%NBA%' "
                "OR series_name LIKE '%乒联%'")
    conn.commit()
    print('② 体育演出与 series 已删除')

    # 4) CBA 合并为一个 series
    cur.execute("SELECT series_id, series_name FROM show_series WHERE series_name LIKE '%CBA%' OR series_name LIKE '%篮球%'")
    cba_series = cur.fetchall()
    if cba_series:
        keep = cba_series[0]['series_id']
        for s in cba_series[1:]:
            cur.execute("UPDATE show_item SET series_id=%s WHERE series_id=%s", (keep, s['series_id']))
            cur.execute("DELETE FROM show_series WHERE series_id=%s", (s['series_id'],))
        cur.execute("UPDATE show_series SET series_name='CBA 职业篮球联赛', main_artist='CBA联赛' WHERE series_id=%s", (keep,))
        print('② CBA 系列已合并为 series_id=%s' % keep)
    else:
        cur.execute("INSERT INTO show_series(series_name,category_id,main_artist,poster_url,description) "
                    "VALUES('CBA 职业篮球联赛',3,'CBA联赛','/static/img/basket1.jpg','CBA 职业篮球联赛。')")
        keep = cur.lastrowid
        if cba_shows:
            for s in cba_shows:
                cur.execute("UPDATE show_item SET series_id=%s WHERE show_id=%s", (keep, s['show_id']))
        print('② CBA 系列新建 series_id=%s' % keep)
    conn.commit()

    # 5) 歌手聚合：每歌手一个 series，把所有该歌手 show 归入
    cur.execute("SELECT show_id, show_name, series_id FROM show_item WHERE category_id=1")
    concert_shows = cur.fetchall()
    artist_series = {}
    for artist in CONCERT_ARTISTS:
        # 匹配：show_name 以 "artist·" 开头 或 包含 artist 且含《或"演唱会"
        matched = [s for s in concert_shows
                   if s['show_name'].startswith(artist + '·')
                   or (artist in s['show_name'] and ('《' in s['show_name'] or '演唱会' in s['show_name'] or artist == 'Taylor Swift'))]
        if not matched:
            continue
        series_name = artist + ' 巡回演唱会'
        cur.execute("SELECT series_id FROM show_series WHERE series_name=%s", (series_name,))
        exist = cur.fetchone()
        if exist:
            sid = exist['series_id']
        else:
            cur.execute("INSERT INTO show_series(series_name,category_id,main_artist,poster_url,description) "
                        "VALUES(%s,1,%s,%s,%s)",
                        (series_name, artist, '/static/img/concert1.jpg', series_name + '。'))
            sid = cur.lastrowid
        for s in matched:
            cur.execute("UPDATE show_item SET series_id=%s WHERE show_id=%s", (sid, s['show_id']))
        artist_series[artist] = sid
        print('③ %s 巡回演唱会 series=%s，归入 %d 场' % (artist, sid, len(matched)))
    conn.commit()

    # 6) 删除旧的"XX《主题》演唱会"孤立 series（它们已被并入歌手系列，若 series 下已无演出则删）
    cur.execute("SELECT series_id FROM show_series WHERE category_id=1 "
                "AND NOT EXISTS (SELECT 1 FROM show_item WHERE show_item.series_id=show_series.series_id)")
    for r in cur.fetchall():
        cur.execute("DELETE FROM show_series WHERE series_id=%s", (r['series_id'],))

    # 7) 重建 sales_daily + 刷场次状态
    cur.execute("TRUNCATE TABLE sales_daily")
    cur.execute("""INSERT INTO sales_daily(stat_date,order_count,ticket_count,total_amount)
                   SELECT DATE(pay_time), COUNT(*), SUM(ticket_count), SUM(total_amount)
                   FROM ticket_order WHERE order_status=2 AND pay_time IS NOT NULL
                   GROUP BY DATE(pay_time)""")
    cur.execute("UPDATE show_session SET sale_status=4 WHERE show_time<=NOW()")
    cur.execute("""UPDATE show_session se SET se.sale_status=3
                   WHERE se.show_time>NOW()
                     AND EXISTS (SELECT 1 FROM ticket_tier t WHERE t.session_id=se.session_id)
                     AND NOT EXISTS (SELECT 1 FROM ticket_tier t
                                     WHERE t.session_id=se.session_id AND t.total_seats-t.sold_seats>0)""")
    cur.execute("""UPDATE show_session se SET se.sale_status=2
                   WHERE se.show_time>NOW() AND se.sale_start<=NOW()
                     AND EXISTS (SELECT 1 FROM ticket_tier t
                                 WHERE t.session_id=se.session_id AND t.total_seats-t.sold_seats>0)""")
    cur.execute("""UPDATE show_session se SET se.sale_status=1
                   WHERE se.show_time>NOW() AND se.sale_start>NOW()
                     AND EXISTS (SELECT 1 FROM ticket_tier t
                                 WHERE t.session_id=se.session_id AND t.total_seats-t.sold_seats>0)""")
    conn.commit()

    # 汇总
    cur.execute("SELECT COUNT(*) c FROM show_item")
    print('执行完成！剩余演出:', cur.fetchone()['c'], '场')
    cur.execute("SELECT COUNT(*) c FROM show_series")
    print('剩余巡演:', cur.fetchone()['c'], '个')
    cur.execute("SELECT COUNT(*) c FROM ticket_order")
    print('剩余订单:', cur.fetchone()['c'], '笔')
    conn.close()


if __name__ == '__main__':
    main()
