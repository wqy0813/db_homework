# -*- coding: utf-8 -*-
"""数据库访问层：统一连接与查询，供页面路由与 /api 蓝图复用。"""
import pymysql
from pymysql.cursors import DictCursor

from config import DB_CONFIG

PLACEHOLDER_HASH = '$2b$10$0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ'
ID_TYPE_NAMES = {1: '身份证', 2: '护照', 3: '港澳通行证', 4: '台胞证', 5: '军官证'}
STATUS_NAMES = {1: '预售中', 2: '售票中', 3: '售罄', 4: '已结束'}
ORDER_STATUS_NAMES = {1: '待支付', 2: '已支付', 3: '已取消', 4: '已退款'}


def get_conn():
    return pymysql.connect(cursorclass=DictCursor, autocommit=False, **DB_CONFIG)


def q(sql, args=(), one=False):
    """查询（只读，自动关连接）。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        conn.close()


def execute(sql, args=()):
    """写操作（自动提交），返回 lastrowid。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            conn.commit()
            return cur.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def verify_password(stored_hash, input_pw):
    """占位哈希放行演示口令 123456；真实 bcrypt 走 werkzeug 校验。"""
    if not stored_hash:
        return False
    if stored_hash == PLACEHOLDER_HASH:
        return input_pw == '123456'
    try:
        from werkzeug.security import check_password_hash
        return check_password_hash(stored_hash, input_pw)
    except Exception:
        return False


def hash_password(input_pw):
    """注册时生成口令哈希，与 verify_password（werkzeug）配套。

    注意：werkzeug 哈希长度约 100+ 字符，需要 password_hash 列为 VARCHAR(255)，
    已有数据库的升级 SQL 见 sql/migrations/20261016_integrate_members.sql。
    """
    from werkzeug.security import generate_password_hash
    return generate_password_hash(input_pw)
