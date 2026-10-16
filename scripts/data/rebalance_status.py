# -*- coding: utf-8 -*-
"""按场次时间、开售时间和余票重算演出销售状态。

规则：已结束场次为已结束（4）；卖完的未来场次为售罄（3）；
每个城市站按各自的开售时间独立在售（2）或预售（1），不限制同一巡演的在售站数。
无余票且已设置票档的未来场次为售罄（3）。脚本可重复执行，--dry-run 只预览。
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

import pymysql
from pymysql.cursors import DictCursor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend"))
from config import DB_CONFIG  # noqa: E402


def load_rows(cur):
    cur.execute(
        """
        SELECT sh.series_id, sh.show_id, se.session_id, se.show_time, se.sale_start,
               se.sale_status,
               COUNT(t.tier_id) AS tier_count,
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
    """返回各场次状态，并按巡演或单场演出汇总全部在售站点。"""
    selected = defaultdict(set)
    result = {}
    for row in rows:
        has_tiers = int(row.get("tier_count", 1 if row["total_seats"] else 0)) > 0
        if row["show_time"] <= now:
            status = 4
        elif has_tiers and int(row["remain"]) <= 0:
            status = 3
        else:
            status = 2 if row["sale_start"] <= now else 1
        result[row["session_id"]] = status
        if status == 2:
            key = ("series", row["series_id"]) if row["series_id"] is not None else ("show", row["show_id"])
            selected[key].add(row["show_id"])
    return result, selected


def validate(cur, now):
    errors = []
    cur.execute(
        """
        SELECT COUNT(*) AS c FROM show_session WHERE sale_start >= show_time
        """
    )
    release_order_errors = cur.fetchone()["c"]
    if release_order_errors:
        errors.append("开售时间不早于开演时间: %s" % release_order_errors)

    cur.execute(
        """
        SELECT COUNT(*) AS c FROM show_session se
        WHERE se.show_time > %s AND se.sale_start <= %s AND se.sale_status = 1
          AND (NOT EXISTS (SELECT 1 FROM ticket_tier t WHERE t.session_id=se.session_id)
               OR EXISTS (SELECT 1 FROM ticket_tier t WHERE t.session_id=se.session_id
                          AND t.total_seats>t.sold_seats))
        """, (now, now)
    )
    missed_release = cur.fetchone()["c"]
    if missed_release:
        errors.append("已到开售时间却仍为预售的场次: %s" % missed_release)

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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
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
