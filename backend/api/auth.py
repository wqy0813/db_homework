# -*- coding: utf-8 -*-
"""认证接口：登录、登出、当前用户、注册。"""
import re

import pymysql
from flask import Blueprint, request, session

from db import q, execute, hash_password
from .helpers import ok, fail, current_user, login_user

auth_bp = Blueprint('api_auth', __name__)

USERNAME_RE = re.compile(r'^[A-Za-z0-9_\u4e00-\u9fa5]{2,50}$')
PHONE_RE = re.compile(r'^1\d{10}$')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


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


@auth_bp.route('/register', methods=['POST'])
def register():
    """普通用户注册：只写 app_user，任何情况下不会创建管理员。"""
    body = request.get_json(silent=True) or request.form
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''
    confirm = body.get('confirm_password') or ''
    phone = (body.get('phone') or '').strip()
    email = (body.get('email') or '').strip() or None

    if not username or not password:
        return fail('请输入用户名和密码')
    if not USERNAME_RE.fullmatch(username):
        return fail('用户名应为 2-50 个字符，仅限中文、字母、数字或下划线')
    if not (6 <= len(password) <= 64):
        return fail('密码长度应为 6-64 个字符')
    if password != confirm:
        return fail('两次输入的密码不一致')
    if not PHONE_RE.fullmatch(phone):
        return fail('手机号格式不正确（11 位数字，1 开头）')
    if email and not EMAIL_RE.fullmatch(email):
        return fail('邮箱格式不正确')

    if q("SELECT 1 FROM app_user WHERE username=%s", (username,), one=True):
        return fail('该用户名已被注册')
    if q("SELECT 1 FROM app_user WHERE phone=%s", (phone,), one=True):
        return fail('该手机号已被注册')

    try:
        uid = execute(
            "INSERT INTO app_user(username,password_hash,phone,email,status) VALUES(%s,%s,%s,%s,1)",
            (username, hash_password(password), phone, email))
    except pymysql.err.IntegrityError:
        return fail('该用户名或手机号已被注册')
    except pymysql.err.DataError:
        return fail('注册失败：数据库 password_hash 字段长度不足，'
                    '请联系管理员按 docs/注册功能数据库升级说明.md 执行升级')
    except Exception as e:
        return fail('注册失败：%s' % e)
    return ok({'user_id': uid}, msg='注册成功，请使用新账号登录')


@auth_bp.route('/me')
def me():
    u = current_user()
    if not u:
        return fail('未登录', 401)
    return ok({'user': u})
