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


def cleanup_batch(cur, order_prefix, user_prefix, poster_urls=(), poster_like=None):
    """删除本批次演出及订单；带有普通订单的演出整体保留。"""
    if poster_like is not None:
        poster_where = 's.poster_url LIKE %s'
        params = [poster_like]
    else:
        poster_where = 's.poster_url IN (' + ','.join(['%s'] * len(poster_urls)) + ')'
        params = list(poster_urls)
    cur.execute("""SELECT s.show_id FROM show_item s
                   WHERE s.show_id>8 AND """ + poster_where + """
                     AND NOT EXISTS (
                       SELECT 1 FROM ticket_order o
                       JOIN show_session se ON se.session_id=o.session_id
                       WHERE se.show_id=s.show_id AND o.order_no NOT LIKE %s)
                   FOR UPDATE""", params + [order_prefix + '%'])
    shows = [row[0] for row in cur.fetchall()]
    if shows:
        marks = ','.join(['%s'] * len(shows))
        cur.execute("""DELETE oi FROM order_item oi
                       JOIN ticket_order o ON o.order_id=oi.order_id
                       JOIN show_session se ON se.session_id=o.session_id
                       WHERE se.show_id IN (""" + marks + ') AND o.order_no LIKE %s',
                    shows + [order_prefix + '%'])
        cur.execute("""DELETE o FROM ticket_order o
                       JOIN show_session se ON se.session_id=o.session_id
                       WHERE se.show_id IN (""" + marks + ') AND o.order_no LIKE %s',
                    shows + [order_prefix + '%'])
        cur.execute("""DELETE pr FROM purchase_request pr
                       JOIN app_user u ON u.user_id=pr.user_id
                       JOIN show_session se ON se.session_id=pr.session_id
                       WHERE se.show_id IN (""" + marks + ''')
                         AND u.username REGEXP %s AND u.password_hash=%s''',
                    shows + ['^' + user_prefix + '[0-9]{6}$', PLACEHOLDER_HASH])
        cur.execute('DELETE FROM ticket_tier WHERE session_id IN (SELECT session_id FROM show_session WHERE show_id IN (' + marks + '))', shows)
        cur.execute('DELETE FROM show_session WHERE show_id IN (' + marks + ')', shows)
        cur.execute('DELETE FROM show_image WHERE show_id IN (' + marks + ')', shows)
        cur.execute('DELETE FROM show_item WHERE show_id IN (' + marks + ')', shows)
    cur.execute("""DELETE a FROM attendee a JOIN app_user u ON u.user_id=a.user_id
                   WHERE u.username REGEXP %s AND u.password_hash=%s
                     AND a.id_no LIKE %s
                     AND NOT EXISTS (SELECT 1 FROM order_item oi WHERE oi.attendee_id=a.attendee_id)""",
                ('^' + user_prefix + '[0-9]{6}$', PLACEHOLDER_HASH, order_prefix + '%'))
    return len(shows)
