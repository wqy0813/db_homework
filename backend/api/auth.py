# -*- coding: utf-8 -*-
"""认证接口：登录、登出、当前用户。"""
from flask import Blueprint, request, session

from .helpers import ok, fail, current_user, login_user

auth_bp = Blueprint('api_auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    body = request.get_json(silent=True) or request.form
    role = body.get('role', 'user')
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''
    if not username or not password:
        return fail('请输入用户名和密码')
    user, err = login_user(role, username, password)
    if err:
        return fail('登录失败：%s' % err)
    session['user'] = user
    return ok({'user': user}, msg='登录成功')


@auth_bp.route('/logout', methods=['POST', 'GET'])
def logout():
    session.clear()
    return ok(msg='已退出')


@auth_bp.route('/me')
def me():
    u = current_user()
    if not u:
        return fail('未登录', 401)
    return ok({'user': u})
