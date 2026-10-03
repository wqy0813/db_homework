# -*- coding: utf-8 -*-
"""
演出门票销售系统 —— Flask 后端（新版前端版本）
新版 Vue 前端入口：http://127.0.0.1:5000/app/（根路径 / 自动跳转到 /app/）
REST API：http://127.0.0.1:5000/api/...（由 api/ 蓝图提供）
旧版 Jinja2 页面已移除；当前只提供 REST API 和 Vue 静态托管。

演示账号：用户 zhang_san / li_si / wang_wu / zhao_liu / chen_qi，管理员 admin；口令统一 123456。
运行：python app.py，浏览器打开 http://127.0.0.1:5000/
"""
import os

from flask import (Flask, request, redirect)

from config import SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,
)

# 注册 REST API 蓝图（新版前端全部走 /api）
from api import register_apis
register_apis(app)


def _allowed_origin(origin):
    if not origin:
        return None
    configured = os.environ.get(
        'CORS_ORIGINS',
        'http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174'
    )
    return origin if origin in {x.strip() for x in configured.split(',') if x.strip()} else None

# 开发期前后端分离：允许 Vite(5173) 跨域并携带 cookie（session）
@app.before_request
def _cors_preflight():
    if request.method == 'OPTIONS':
        origin = _allowed_origin(request.headers.get('Origin'))
        if origin:
            from flask import make_response
            r = make_response('', 204)
            r.headers['Access-Control-Allow-Origin'] = origin
            r.headers['Access-Control-Allow-Credentials'] = 'true'
            r.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
            r.headers['Access-Control-Allow-Headers'] = request.headers.get(
                'Access-Control-Request-Headers', 'Content-Type'
            )
            r.headers['Vary'] = 'Origin'
            return r


@app.after_request
def _cors(resp):
    origin = _allowed_origin(request.headers.get('Origin'))
    if origin:
        resp.headers['Access-Control-Allow-Origin'] = origin
        resp.headers['Access-Control-Allow-Credentials'] = 'true'
        resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = request.headers.get(
            'Access-Control-Request-Headers', 'Content-Type'
        )
        resp.headers['Vary'] = 'Origin'
    return resp


# ---------------------------------------------------------------------------
# 根路径直接进入新版前端（旧版 Jinja2 页面已下线）
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return redirect('/app/')


# ---------------------------------------------------------------------------
# 托管打包后的 Vue 前端（新版前端访问入口：/app/，hash 路由如 /app/#/shows）
# ---------------------------------------------------------------------------
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static_web')


@app.route('/app/')
@app.route('/app/<path:path>')
def spa_app(path='index.html'):
    from flask import send_from_directory
    full = os.path.join(WEB_DIR, path)
    if os.path.isfile(full):
        response = send_from_directory(WEB_DIR, path)
        # The HTML entry point must be revalidated after each frontend build;
        # hashed JS/CSS assets remain safe to cache independently.
        if path == 'index.html':
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response
    index = os.path.join(WEB_DIR, 'index.html')
    if os.path.isfile(index):
        response = send_from_directory(WEB_DIR, 'index.html')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return redirect('/app/')


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
