# -*- coding: utf-8 -*-
"""API 共用工具：统一响应、登录态/角色校验、登录信息。"""
from functools import wraps
from flask import session, jsonify, request

from db import verify_password, q


def ok(data=None, **extra):
    resp = {'code': 0, 'msg': 'ok'}
    if data is not None:
        resp['data'] = data
    resp.update(extra)
    return jsonify(resp)


def fail(msg, code=1):
    return jsonify({'code': code, 'msg': msg})


def current_user():
    return session.get('user')


def require_login(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            u = current_user()
            if not u:
                return fail('未登录', 401)
            if role and u['role'] != role:
                return fail('无权访问', 403)
            return fn(*args, **kwargs)
        return wrapper
    return deco


def login_user(role, username, password):
    """统一登录校验，返回 (user_dict, error_msg)。"""
    if role == 'admin':
        row = q("SELECT * FROM admin WHERE username=%s", (username,), one=True)
        if row and verify_password(row['password_hash'], password):
            return {'role': 'admin', 'id': row['admin_id'],
                    'name': row['real_name'] or row['username']}, None
    else:
        row = q("SELECT * FROM app_user WHERE username=%s", (username,), one=True)
        if row and row['status'] == 1 and verify_password(row['password_hash'], password):
            return {'role': 'user', 'id': row['user_id'], 'name': row['username']}, None
    return None, '用户名或密码错误'
