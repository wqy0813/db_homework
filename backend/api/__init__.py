# -*- coding: utf-8 -*-
"""REST API 蓝图包。第 2 期后端 API 化，供 Vue 前端调用。"""
from .auth import auth_bp
from .shows import shows_bp
from .orders import orders_bp
from .profile import profile_bp
from .admin import admin_bp
from .stats import stats_bp


def register_apis(app):
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(shows_bp, url_prefix='/api')
    app.register_blueprint(orders_bp, url_prefix='/api')
    app.register_blueprint(profile_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api')
    app.register_blueprint(stats_bp, url_prefix='/api')
