# -*- coding: utf-8 -*-
"""第 4 期：批量聚合生成器数据到巡演 series。
对 show_item 中未归属的演出，按名称中的 IP 关键词分组，每组建一个 show_series。
运行：python scripts/data/group_series.py（连 3306 库，可重复执行）
"""
import os
import sys

import pymysql

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))
from config import DB_CONFIG  # noqa: E402
from posters import collected_poster  # noqa: E402

# (关键词, 规范巡演名, 类型id)
IP_KEYWORDS = [
    ('林俊杰', '林俊杰《JJ20》世界巡回演唱会', 1),
    ('五月天', '五月天《好好好想见到你》演唱会', 1),
    ('陈奕迅', '陈奕迅《Fear and Dreams》演唱会', 1),
    ('王菲', '王菲《幻乐一场》演唱会', 1),
    ('薛之谦', '薛之谦《天外来物》巡回演唱会', 1),
    ('邓紫棋', '邓紫棋《GLORIA》世界巡回演唱会', 1),
    ('李荣浩', '李荣浩《纵横四海》演唱会', 1),
    ('华晨宇', '华晨宇《火星》演唱会', 1),
    ('Taylor Swift', 'Taylor Swift 时代巡回演唱会', 1),
    ('刘德华', '刘德华《今天》巡回演唱会', 1),
    ('梁静茹', '梁静茹《当我们谈论爱情》演唱会', 1),
    ('蔡依林', '蔡依林《Ugly Beauty》演唱会', 1),
    ('毛不易', '毛不易《幼鸟指南》巡回演唱会', 1),
    ('张杰', '张杰《未LIVE》巡回演唱会', 1),
    ('周杰伦', '周杰伦《嘉年华》世界巡回演唱会', 1),
    ('张学友', '张学友《60+》巡回演唱会', 1),
    ('茶馆', '话剧《茶馆》', 2),
    ('暗恋桃花源', '话剧《暗恋桃花源》', 2),
    ('白鹿原', '话剧《白鹿原》', 2),
    ('戏台', '话剧《戏台》', 2),
    ('歌剧魅影', '音乐剧《歌剧魅影》', 2),
    ('巴黎圣母院', '音乐剧《巴黎圣母院》', 2),
    ('猫', '音乐剧《猫》Cats', 2),
    ('雷雨', '话剧《雷雨》', 2),
    ('中超', '中超联赛 主场赛事', 3),
    ('CBA', 'CBA 职业篮球联赛', 3),
    ('NBA', 'NBA 中国赛', 3),
    ('乒联', '国际乒联世界巡回赛', 3),
    ('排球', '排球超级联赛', 3),
    ('梵高', '梵高《星夜》光影艺术展', 5),
    ('teamLab', 'teamLab 无界美术馆', 5),
    ('故宫', '故宫文物特展', 5),
    ('敦煌', '敦煌艺术大展', 5),
    ('恐龙', '恐龙化石科普展', 5),
    ('太空', '太空探索沉浸展', 5),
    ('莫奈', '莫奈《光影》沉浸式艺术展', 5),
    ('久石让', '久石让·宫崎骏动漫音乐会', 6),
    ('王羽佳', '王羽佳钢琴独奏音乐会', 6),
    ('郎朗', '郎朗钢琴独奏音乐会', 6),
    ('天鹅湖', '芭蕾舞剧《天鹅湖》', 7),
    ('胡桃夹子', '芭蕾舞剧《胡桃夹子》', 7),
    ('朱鹮', '舞剧《朱鹮》', 7),
    ('只此青绿', '舞剧《只此青绿》', 7),
]

def main(show_ids=None, include_unmapped=False):
    conn = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **DB_CONFIG)
    cur = conn.cursor()
    sql = "SELECT show_id, show_name, category_id, poster_url FROM show_item WHERE series_id IS NULL"
    args = ()
    if show_ids is not None:
        args = tuple(show_ids)
        sql += (' AND show_id IN (' + ','.join(['%s'] * len(args)) + ')') if args else ' AND 1=0'
    cur.execute(sql, args)
    rows = cur.fetchall()
    print('待聚合演出数:', len(rows))

    # 预填已存在的 series（seed 建的 8 个），避免同名冲突
    cur.execute("SELECT series_id, series_name FROM show_series")
    series_cache = {}
    for s in cur.fetchall():
        series_cache[s['series_name']] = s['series_id']

    created = 0
    grouped = 0
    assigned = set()
    for kw, series_name, cat in IP_KEYWORDS:
        for r in rows:
            if kw in r['show_name'] and r['category_id'] == cat and r['show_id'] not in assigned:
                if series_name not in series_cache:
                    poster_url = collected_poster(series_name, cat, artist=kw)
                    if poster_url is None:
                        raise RuntimeError(
                            f'系列缺少真实海报映射：category={cat}, keyword={kw}, series={series_name}'
                        )
                    cur.execute(
                        "INSERT INTO show_series(series_name,category_id,main_artist,poster_url,description) "
                        "VALUES(%s,%s,%s,%s,%s)",
                        (series_name, cat, kw, poster_url, series_name + '，全国巡演中。'))
                    series_id = cur.lastrowid
                    series_cache[series_name] = series_id
                    created += 1
                cur.execute("UPDATE show_item SET series_id=%s WHERE show_id=%s",
                            (series_cache[series_name], r['show_id']))
                grouped += 1
                assigned.add(r['show_id'])
    if include_unmapped:
        for row in rows:
            if row['show_id'] in assigned:
                continue
            name = row['show_name'].rsplit('·', 1)[0].strip()
            if name not in series_cache:
                poster_url = collected_poster(name, row['category_id'], artist=name) or row['poster_url']
                cur.execute("""INSERT INTO show_series(series_name,category_id,main_artist,poster_url,description)
                               VALUES(%s,%s,%s,%s,%s)""",
                            (name, row['category_id'], name, poster_url, name + '，欢迎观演。'))
                series_cache[name] = cur.lastrowid
                created += 1
            cur.execute('UPDATE show_item SET series_id=%s WHERE show_id=%s',
                        (series_cache[name], row['show_id']))
            grouped += 1
    conn.commit()
    print('新建巡演:', created, ' 聚合演出:', grouped)
    cur.execute("SELECT COUNT(*) AS c FROM show_series")
    print('show_series 总数:', cur.fetchone()['c'])
    conn.close()


if __name__ == '__main__':
    main()
