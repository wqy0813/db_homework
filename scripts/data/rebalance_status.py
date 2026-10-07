# -*- coding: utf-8 -*-
"""按场次时间、开售时间和余票重算演出销售状态。

规则：已结束场次为已结束（4）；卖完的未来场次为售罄（3）；
一个系列最多选择一个有余票且已开售的城市站为在售（2）；
其余未结束且有余票的站点为预售（1），无余票站点为售罄（3）。脚本可重复执行，--dry-run 只预览。
"""
from __future__ import annotations

import argparse
import io
import os
import sys
from collections import defaultdict

import pymysql
from pymysql.cursors import DictCursor

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend"))
from config import DB_CONFIG  # noqa: E402


def load_rows(cur):
    cur.execute(
        """
        SELECT sh.series_id, sh.show_id, se.session_id, se.show_time, se.sale_start,
               se.sale_status,
               COALESCE(SUM(t.total_seats), 0) AS total_seats,
               COALESCE(SUM(t.sold_seats), 0) AS sold_seats,
               COALESCE(SUM(GREATEST(t.total_seats - t.sold_seats, 0)), 0) AS remain
        FROM show_item sh
        JOIN show_session se ON se.show_id = sh.show_id
        LEFT JOIN ticket_tier t ON t.session_id = se.session_id
        GROUP BY sh.series_id, sh.show_id, se.session_id, se.show_time, se.sale_start, se.sale_status
        ORDER BY sh.series_id, se.show_time, se.session_id
        """
    )
    return cur.fetchall()


def plan_statuses(rows, now):
    """返回 session_id -> new_status，并返回每个系列选中的在售 show_id。"""
    stations = defaultdict(list)
    for row in rows:
        # 未归入系列的演出各自独立处理，不和其它未分组演出抢唯一在售名额。
        key = ("series", row["series_id"]) if row["series_id"] is not None else ("show", row["show_id"])
        stations[key].append(row)

    selected = {}
    for key, station_rows in stations.items():
        candidates = []
        for show_id in {r["show_id"] for r in station_rows}:
            future = [r for r in station_rows if r["show_id"] == show_id and r["show_time"] > now]
            if any(r["sale_start"] <= now and int(r["remain"]) > 0 for r in future):
                candidates.append((min(r["show_time"] for r in future), show_id))
        if candidates:
            # 最近一站优先；show_id 保证同一日期下结果稳定。
            selected[key] = min(candidates)[1]

    result = {}
    for key, station_rows in stations.items():
        chosen_show = selected.get(key)
        for row in station_rows:
            if row["show_time"] <= now:
                status = 4
            elif int(row["remain"]) <= 0:
                status = 3
            elif chosen_show == row["show_id"] and row["sale_start"] <= now:
                status = 2
            else:
                # 其它站点即使已经到开售时间，也降为预售，确保系列内最多一个在售站。
                status = 1
            result[row["session_id"]] = status
    return result, selected


def validate(cur, now):
    errors = []
    cur.execute(
        """
        SELECT COUNT(*) AS c FROM (
          SELECT show_time, sale_start,
                 LAG(show_time) OVER (ORDER BY show_time, session_id) AS prev_show_time,
                 LAG(sale_start) OVER (ORDER BY show_time, session_id) AS prev_sale_start
          FROM show_session
        ) ordered_sessions
        WHERE show_time > prev_show_time AND sale_start < prev_sale_start
        """
    )
    release_order_errors = cur.fetchone()["c"]
    if release_order_errors:
        errors.append("开演更早的场次却更晚开售: %s" % release_order_errors)

    cur.execute(
        """
        SELECT series_id, SUM(show_status = 2) AS onsale_count
        FROM v_show_list
        WHERE series_id IS NOT NULL
        GROUP BY series_id
        HAVING onsale_count > 1
        """
    )
    duplicate_series = cur.fetchall()
    if duplicate_series:
        errors.append("系列存在多个在售站点: %s" % duplicate_series[:5])

    cur.execute("SELECT COUNT(*) AS c FROM show_session WHERE show_time <= %s AND sale_status <> 4", (now,))
    past_open = cur.fetchone()["c"]
    if past_open:
        errors.append("已结束但状态不是 4 的场次: %s" % past_open)

    cur.execute(
        "SELECT COUNT(*) AS c FROM show_session WHERE show_time > %s AND sale_status = 4",
        (now,),
    )
    future_ended = cur.fetchone()["c"]
    if future_ended:
        errors.append("尚未开演但状态为已结束的场次: %s" % future_ended)

    cur.execute(
        """
        SELECT COUNT(*) AS c
        FROM show_session se
        WHERE se.show_time > %s AND se.sale_status = 3
          AND EXISTS (
            SELECT 1 FROM ticket_tier t
            WHERE t.session_id = se.session_id
              AND t.total_seats - t.sold_seats > 0
          )
        """,
        (now,),
    )
    future_stocked_sold_out = cur.fetchone()["c"]
    if future_stocked_sold_out:
        errors.append("未来售罄场次仍有余票: %s" % future_stocked_sold_out)

    cur.execute(
        """
        SELECT COUNT(*) AS c
        FROM show_session se
        WHERE se.sale_status = 2
          AND (se.show_time <= %s OR se.sale_start > %s)
        """,
        (now, now),
    )
    invalid_onsale = cur.fetchone()["c"]
    if invalid_onsale:
        errors.append("售票中场次尚未开售或已结束: %s" % invalid_onsale)

    cur.execute(
        """
        SELECT sh.show_id, sh.series_id,
               SUM(CASE WHEN se.show_time > %s
                        THEN GREATEST(t.total_seats-t.sold_seats, 0) ELSE 0 END) AS future_remain
        FROM show_item sh
        JOIN show_session se ON se.show_id = sh.show_id
        LEFT JOIN ticket_tier t ON t.session_id = se.session_id
        GROUP BY sh.show_id, sh.series_id
        HAVING MAX(se.sale_status = 3) = 1
           AND MAX(se.sale_status IN (1, 2)) = 0
           AND future_remain > 0
        """,
        (now,),
    )
    inconsistent_soldout = cur.fetchall()
    if inconsistent_soldout:
        errors.append("全售罄站点仍有余票: %s" % inconsistent_soldout[:5])
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只计算和打印变更，不写入数据库")
    args = parser.parse_args()

    conn = pymysql.connect(cursorclass=DictCursor, autocommit=False, **DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute("SELECT NOW() AS now")
        now = cur.fetchone()["now"]
        rows = load_rows(cur)
        plan, selected = plan_statuses(rows, now)
        before = defaultdict(int)
        after = defaultdict(int)
        changed = 0
        for row in rows:
            before[int(row["sale_status"])] += 1
            after[plan[row["session_id"]]] += 1
            changed += int(row["sale_status"] != plan[row["session_id"]])

        print("数据库时间:", now)
        print("场次数:", len(rows), "计划变更:", changed)
        print("原状态分布:", dict(sorted(before.items())))
        print("计划状态分布:", dict(sorted(after.items())))
        print("有在售站的系列/未分组演出:", len(selected))

        if args.dry_run:
            print("DRY-RUN：未写入数据库")
            return

        for session_id, status in plan.items():
            cur.execute("UPDATE show_session SET sale_status=%s WHERE session_id=%s", (status, session_id))
        errors = validate(cur, now)
        if errors:
            conn.rollback()
            raise RuntimeError("状态校验失败，已回滚:\n- " + "\n- ".join(errors))
        conn.commit()
        print("已提交状态更新")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
