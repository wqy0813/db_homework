"""演示批次清理：只处理生成器标识明确的数据，保留注册用户和正常订单。"""
from db import PLACEHOLDER_HASH


def demo_users(cur, prefix):
    cur.execute("""SELECT user_id FROM app_user
                   WHERE username REGEXP %s AND password_hash=%s ORDER BY user_id""",
                ('^' + prefix + '[0-9]{6}$', PLACEHOLDER_HASH))
    return [row[0] for row in cur.fetchall()]


def demo_addresses(cur, prefix):
    cur.execute("""SELECT a.user_id,a.address_id FROM shipping_address a
                   JOIN app_user u ON u.user_id=a.user_id
                   WHERE u.username REGEXP %s AND u.password_hash=%s
                   ORDER BY a.is_default DESC,a.address_id""",
                ('^' + prefix + '[0-9]{6}$', PLACEHOLDER_HASH))
    result = {}
    for uid, address_id in cur.fetchall():
        result.setdefault(uid, address_id)
    return result


def cleanup_batch(cur, order_prefix, user_prefix, poster_urls=(), poster_like=None, venue_like=None):
    """删除可明确识别的批量演出及其派生数据；带有普通订单的演出整体保留。"""
    if venue_like is not None:
        show_where = """EXISTS (
            SELECT 1 FROM show_session se
            JOIN venue v ON v.venue_id=se.venue_id
            WHERE se.show_id=s.show_id AND v.venue_name LIKE %s)"""
        selector_params = [venue_like]
    elif poster_like is not None:
        show_where = 's.poster_url LIKE %s'
        selector_params = [poster_like]
    elif poster_urls:
        show_where = 's.poster_url IN (' + ','.join(['%s'] * len(poster_urls)) + ')'
        selector_params = list(poster_urls)
    else:
        # gen_more_data.py 的 B 批次没有独立海报标记，因此只按显式批次订单识别。
        # 不能仅凭演示用户的 purchase_request 反推演出，否则可能误伤正常演出。
        show_where = """EXISTS (
            SELECT 1 FROM ticket_order o
            JOIN show_session se ON se.session_id=o.session_id
            WHERE se.show_id=s.show_id AND o.order_no LIKE %s)"""
        selector_params = [order_prefix + '%']
    # 只清理没有任何非本批次订单的演出，避免误删正常数据。
    cur.execute("""SELECT s.show_id
                   FROM show_item s
                   WHERE s.show_id>8 AND """ + show_where + """
                     AND NOT EXISTS (
                       SELECT 1 FROM ticket_order o
                       JOIN show_session se ON se.session_id=o.session_id
                       WHERE se.show_id=s.show_id AND o.order_no NOT LIKE %s)
                   FOR UPDATE""", selector_params + [order_prefix + '%'])
    shows = [row[0] for row in cur.fetchall()]
    series_ids = []
    if shows:
        marks = ','.join(['%s'] * len(shows))
        cur.execute("""SELECT DISTINCT series_id FROM show_item
                       WHERE show_id IN (""" + marks + """) AND series_id IS NOT NULL""", shows)
        series_ids = [row[0] for row in cur.fetchall()]
        # 选择条件已经保证这些演出不存在非本批次订单，因此这里删除该演出下的全部订单。
        cur.execute("""DELETE oi FROM order_item oi
                       JOIN ticket_order o ON o.order_id=oi.order_id
                       JOIN show_session se ON se.session_id=o.session_id
                       WHERE se.show_id IN (""" + marks + ")""", shows)
        cur.execute("""DELETE o FROM ticket_order o
                       JOIN show_session se ON se.session_id=o.session_id
                       WHERE se.show_id IN (""" + marks + ")""", shows)
        cur.execute('DELETE FROM purchase_request WHERE session_id IN (SELECT session_id FROM show_session WHERE show_id IN (' + marks + '))', shows)
        cur.execute('DELETE FROM ticket_tier WHERE session_id IN (SELECT session_id FROM show_session WHERE show_id IN (' + marks + '))', shows)
        cur.execute('DELETE FROM show_session WHERE show_id IN (' + marks + ')', shows)
        cur.execute('DELETE FROM show_image WHERE show_id IN (' + marks + ')', shows)
        cur.execute('DELETE FROM show_item WHERE show_id IN (' + marks + ')', shows)

        # 只删除本次选中的巡演中、删完演出后确实已经没有站点的巡演。
        if series_ids:
            series_marks = ','.join(['%s'] * len(series_ids))
            cur.execute("""DELETE ser FROM show_series ser
                           WHERE ser.series_id IN (""" + series_marks + """)
                             AND NOT EXISTS (
                               SELECT 1 FROM show_item s WHERE s.series_id=ser.series_id)""", series_ids)

    # F/u 演示购票人只有在不再被任何订单引用时才清理；真实注册用户和仍被使用的资料保留。
    cur.execute("""DELETE a FROM attendee a JOIN app_user u ON u.user_id=a.user_id
                   WHERE u.username REGEXP %s AND u.password_hash=%s
                     AND a.id_no LIKE %s
                     AND NOT EXISTS (SELECT 1 FROM order_item oi WHERE oi.attendee_id=a.attendee_id)""",
                ('^' + user_prefix + '[0-9]{6}$', PLACEHOLDER_HASH, order_prefix + '%'))
    return len(shows)
