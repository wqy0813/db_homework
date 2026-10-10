# -*- coding: utf-8 -*-
"""Refresh database poster URLs from the collected poster catalog.

Collected originals are served directly from poster_collect through /posters/.
Administrator uploads and external URLs are preserved. Missing legacy local
images are cleared instead of being pointed at files that are no longer shipped.
Run from the project root: python scripts/data/gen_posters.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))

import pymysql
from config import DB_CONFIG  # noqa: E402
from posters import resolve_poster  # noqa: E402


def main():
    conn = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **DB_CONFIG)
    cur = conn.cursor()

    cur.execute("SELECT series_id, series_name, main_artist, category_id, poster_url FROM show_series")
    series_rows = cur.fetchall()
    for row in series_rows:
        poster_url = resolve_poster(
            row['series_name'], row['category_id'], row.get('poster_url'), row.get('main_artist'))
        cur.execute("UPDATE show_series SET poster_url=%s WHERE series_id=%s",
                    (poster_url, row['series_id']))

    cur.execute("""
        SELECT sh.show_id, sh.show_name, sh.category_id, sh.poster_url,
               ser.series_name, ser.main_artist, ser.poster_url AS series_poster_url
        FROM show_item sh
        LEFT JOIN show_series ser ON ser.series_id=sh.series_id
    """)
    show_rows = cur.fetchall()
    for row in show_rows:
        name = row.get('series_name') or row['show_name']
        poster_url = resolve_poster(
            name, row['category_id'], row.get('poster_url'), row.get('main_artist'))
        if not poster_url and row.get('series_poster_url'):
            poster_url = resolve_poster(
                name, row['category_id'], row['series_poster_url'], row.get('main_artist'))
        cur.execute("UPDATE show_item SET poster_url=%s WHERE show_id=%s",
                    (poster_url, row['show_id']))

    conn.commit()
    cur.execute("SELECT COUNT(*) AS n FROM show_series WHERE poster_url LIKE '/posters/%'")
    collected_series = cur.fetchone()['n']
    cur.execute("SELECT COUNT(*) AS n FROM show_item WHERE poster_url LIKE '/posters/%'")
    collected_shows = cur.fetchone()['n']
    print('系列海报映射:', collected_series, '/', len(series_rows))
    print('演出海报映射:', collected_shows, '/', len(show_rows))
    conn.close()


if __name__ == '__main__':
    main()
