# -*- coding: utf-8 -*-
"""探测 zhang_san 的收货地址/购票人/订单，为购票测试选数据。"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
import requests

BASE = 'http://127.0.0.1:5000/api'
s = requests.Session()

r = s.post(BASE + '/login', json={'role': 'user', 'username': 'zhang_san', 'password': '123456'})
print('login:', r.status_code, r.json())

r = s.get(BASE + '/addresses')
print('addresses:', json.dumps(r.json(), ensure_ascii=False)[:2000])

r = s.get(BASE + '/attendees')
print('attendees:', json.dumps(r.json(), ensure_ascii=False)[:2000])

r = s.get(BASE + '/orders')
d = r.json()
print('orders count:', len(d.get('data', {}).get('list', [])))
for o in d.get('data', {}).get('list', [])[:8]:
    print('  order:', o.get('order_no'), o.get('show_name'), o.get('session_id'), o.get('order_status'),
          o.get('ticket_count'), o.get('total_amount'), 'items:', [(i['attendee_name'], i['session_id']) for i in o.get('items', [])])
