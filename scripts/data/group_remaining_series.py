# -*- coding: utf-8 -*-
"""通用聚合：对未归入 series 的演出，按名称前缀（“·”前的赛事/剧目名）分组聚合。
适用：体育（羽毛球大师赛·X站）、话剧（茶馆·X站）、展览、音乐会、舞蹈等所有类型。
规则：分组名 = SUBSTRING_INDEX(show_name,'·',1)；组内 ≥2 站才建 series；
      已归入的（series_id 非空）跳过。dry 模式只统计。
用法：python scripts/data/group_remaining_series.py --dry
      python scripts/data/group_remaining_series.py
"""
import os
import sys
import pymysql

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))
from config import DB_CONFIG  # noqa: E402

DRY = '--dry' in sys.argv

CAT_POSTER = {
    1: '/static/img/concert1.jpg', 2: '/static/img/theater1.jpg', 3: '/static/img/basket1.jpg',
    5: '/static/img/museum1.jpg', 6: '/static/img/piano1.jpg', 7: '/static/img/dance1.jpg',
}


def main():
    conn = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, autocommit=False, **DB_CONFIG)
    cur = conn.cursor()
    # 未归入的演出，排除单场（名称不含"·"的、或含"·"但组内仅1站的）
    cur.execute("""SELECT show_id, show_name, category_id FROM show_item
                   WHERE series_id IS NULL AND show_name LIKE '%·%'""")
    rows = cur.fetchall()
    # 按前缀分组
    groups = {}
    for r in rows:
        g = r['show_name'].split('·')[0].strip()
        if not g:
            continue
        groups.setdefault(g, []).append(r)

    # 只保留 ≥2 站的组
    multi = {g: v for g, v in groups.items() if len(v) >= 2}
    single = {g: v for g, v in groups.items() if len(v) < 2}
    print('=' * 60)
    print('【预演】' if DRY else '【执行】')
    print('=' * 60)
    print('含"·"的未归入演出总数:', len(rows))
    print('将聚合的组（≥2站）:', len(multi), '个，涉及演出', sum(len(v) for v in multi.values()), '场')
    print('单站组（不聚合）:', len(single), '个，涉及演出', sum(len(v) for v in single.values()), '场')
    print('--- 前 20 组 ---')
    for g in sorted(multi, key=lambda x: -len(multi[x]))[:20]:
        cat = multi[g][0]['category_id']
        print('  %s（%d 站, 类型%d）' % (g, len(multi[g]), cat))
    if DRY:
        print()
        print('DRY：确认无误后运行 python scripts/data/group_remaining_series.py')
        conn.close()
        return

    # 执行：每组建一个 series，归入
    created = 0
    grouped = 0
    for g, shows in multi.items():
        cat = shows[0]['category_id']
        series_name = g
        cur.execute("SELECT series_id FROM show_series WHERE series_name=%s", (series_name,))
        exist = cur.fetchone()
        if exist:
            sid = exist['series_id']
        else:
            cur.execute("INSERT INTO show_series(series_name,category_id,main_artist,poster_url,description) "
                        "VALUES(%s,%s,%s,%s,%s)",
                        (series_name, cat, g, CAT_POSTER.get(cat), series_name + '。'))
            sid = cur.lastrowid
            created += 1
        for s in shows:
            cur.execute("UPDATE show_item SET series_id=%s WHERE show_id=%s", (sid, s['show_id']))
            grouped += 1

    # ---- 修补：游离演出（名称无"·站"后缀）按关键词归入已有系列 ----
    # 关键词 -> series 名（精确匹配已有系列）
    STRAY_KEYWORDS = {
        '羽毛球大师赛': '羽毛球大师赛', '网球公开赛': '网球公开赛', '搏击争霸赛': '搏击争霸赛',
        '城市马拉松': '城市马拉松', '排球超级联赛': '排球超级联赛', '电竞大赛': '电竞大赛',
        '猫': '猫', '永不消逝的电波': '永不消逝的电波',
        '维也纳交响': '维也纳交响', '国家大剧院交响': '国家大剧院交响', '柏林爱乐': '柏林爱乐',
        '理查德钢琴': '理查德钢琴', '李云迪钢琴': '李云迪钢琴', '马克西姆钢琴': '马克西姆钢琴',
        '大宅门': '大宅门', '窝头会馆': '窝头会馆', '宝岛一村': '宝岛一村', '西贡小姐': '西贡小姐',
        '如梦之梦': '如梦之梦', '甄嬛传话剧': '甄嬛传话剧',
        '毕加索': '毕加索真迹展', '达利': '达利艺术展', '古埃及': '古埃及文明展',
        '舞俑': '舞俑', '孔子舞剧': '孔子舞剧', '红楼梦舞剧': '红楼梦舞剧',
        '吉赛尔': '吉赛尔', '睡美人': '睡美人', '中国爱乐': '中国爱乐',
    }
    cur.execute("""SELECT show_id, show_name, category_id FROM show_item
                   WHERE series_id IS NULL""")
    stray = cur.fetchall()
    fixed = 0
    for r in stray:
        for kw, series_name in STRAY_KEYWORDS.items():
            if kw in r['show_name']:
                cur.execute("SELECT series_id FROM show_series WHERE series_name=%s", (series_name,))
                hit = cur.fetchone()
                if hit:
                    cur.execute("UPDATE show_item SET series_id=%s WHERE show_id=%s",
                                (hit['series_id'], r['show_id']))
                    fixed += 1
                break
    if fixed:
        print('游离演出修补归入:', fixed, '场')
    conn.commit()
    print('新建 series:', created, ' 归入演出:', grouped, ' 游离修补:', fixed)
    conn.close()


if __name__ == '__main__':
    main()
