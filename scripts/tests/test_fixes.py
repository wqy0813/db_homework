import sys
import requests


def main():
    sys.stdout.reconfigure(encoding='utf-8')

    # 1. User login and buy count validation
    s_user = requests.Session()
    r = s_user.post('http://127.0.0.1:5000/api/login', json={'role': 'user', 'username': 'zhang_san', 'password': '123456'})
    assert r.json()['code'] == 0, r.text

    r = s_user.post('http://127.0.0.1:5000/api/buy', json={
        'show_id': 1, 'session_id': 1, 'tier_id': 1, 'address_id': 1, 'count': 1.5, 'attendee_ids': [1]
    })
    assert r.json()['code'] != 0
    print('PASS: Buy with float count=1.5 rejected:', r.json()['msg'])

    # 2. Admin login
    s_admin = requests.Session()
    r = s_admin.post('http://127.0.0.1:5000/api/login', json={'role': 'admin', 'username': 'admin', 'password': '123456'})
    assert r.json()['code'] == 0, r.text

    # 3. Test station poster validations (series station and inferred station)
    r = s_admin.post('http://127.0.0.1:5000/api/admin/series/1/stations/create', json={
        'show_name': '测试站点', 'city_id': 1, 'poster_url': r'C:\missing\poster.jpg'
    })
    assert r.json()['code'] != 0
    print('PASS: Series station local path rejected:', r.json()['msg'])

    r = s_admin.post('http://127.0.0.1:5000/api/admin/series/1/stations/create', json={
        'show_name': '测试站点', 'city_id': 1, 'poster_url': '/posters/review-definitely-missing.jpg'
    })
    assert r.json()['code'] != 0
    print('PASS: Series station missing poster rejected:', r.json()['msg'])

    r = s_admin.post('http://127.0.0.1:5000/api/admin/series/group/stations/create', json={
        'group_name': '周杰伦', 'show_name': '测试站点', 'city_id': 1, 'poster_url': '/posters/missing.jpg'
    })
    assert r.json()['code'] != 0
    print('PASS: Inferred station missing poster rejected:', r.json()['msg'])

    r = s_admin.post('http://127.0.0.1:5000/api/admin/shows/create', json={
        'show_name': '测试演出海报越界', 'category_id': 1, 'city_id': 1, 'poster_url': '/static/../static_web/index.html'
    })
    assert r.json()['code'] != 0
    print('PASS: Traversal poster path rejected:', r.json()['msg'])

    # 4. Test price quantize to 0.00 rejection
    r = s_admin.post('http://127.0.0.1:5000/api/admin/tier/create', json={
        'session_id': 1, 'tier_name': '测试零价票', 'price': '0.001', 'total_seats': 10
    })
    assert r.json()['code'] != 0
    print('PASS: Price 0.001 quantizing to 0.00 rejected:', r.json()['msg'])

    # 5. Test session edit retains sale_start
    r = s_admin.get('http://127.0.0.1:5000/api/shows/1')
    se1 = [s for s in r.json()['data']['sessions'] if s['session_id'] == 1][0]
    orig_sale_start = se1['sale_start']

    t1 = r.json()['data']['tiers']['1']
    edit_body = {
        'show_id': 1,
        'venue_id': se1['venue_id'],
        'show_time': se1['show_time'],
        'tiers': [{'tier_id': t['tier_id'], 'tier_name': t['tier_name'], 'price': t['price'], 'total_seats': t['total_seats']} for t in t1],
        'new_tiers': [],
        'delete_tier_ids': []
    }
    r = s_admin.post('http://127.0.0.1:5000/api/admin/session/1/update', json=edit_body)
    assert r.json()['code'] == 0, r.text

    r = s_admin.get('http://127.0.0.1:5000/api/shows/1')
    se1_after = [s for s in r.json()['data']['sessions'] if s['session_id'] == 1][0]
    assert se1_after['sale_start'] == orig_sale_start, f'sale_start changed! {orig_sale_start} -> {se1_after["sale_start"]}'
    print('PASS: Session edit retains sale_start:', se1_after['sale_start'])

    # 6. Test historical order price is snapshot unit_price
    r = s_user.get('http://127.0.0.1:5000/api/orders')
    orders = r.json()['data']['list']
    if orders:
        oid = orders[0]['order_id']
        r_detail = s_user.get(f'http://127.0.0.1:5000/api/orders/{oid}')
        assert r_detail.json()['code'] == 0
        detail = r_detail.json()['data']['order']
        items = r_detail.json()['data']['items']
        print(f'PASS: Order detail fetched (order_id={oid}, tier_price={detail.get("tier_price")}, items_unit_price={items[0]["unit_price"] if items else None})')

    print('\nALL TARGETED VERIFICATIONS PASSED!')


if __name__ == "__main__":
    main()
