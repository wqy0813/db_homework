# -*- coding: utf-8 -*-
"""数据库连接配置 —— 按你的 MySQL 环境修改本文件即可。
也支持用环境变量覆盖（端口/用户/密码/库名），未设置时用下方默认值。"""
import os

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('DB_PORT', '3306')),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'ticket_sales'),
    'charset': 'utf8mb4',
}

SECRET_KEY = os.environ.get('SECRET_KEY', 'ticket-sales-demo-secret-key-change-me')
