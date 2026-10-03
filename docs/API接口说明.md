# 后端 REST API 接口说明（第 2 期）

Flask 后端在保留原页面路由的同时，新增一组 `/api/*` JSON 接口，供 Vue 前端调用。
- 基础地址：`http://127.0.0.1:5000/api`
- 统一返回：`{ "code": 0, "msg": "ok", "data": {...} }`；`code=0` 成功，`code=401/403` 未登录/无权限，其他为业务失败（错误信息在 `msg`）。
- 登录态：用 Cookie Session（登录后自动带 `session` cookie）；前后端分离开发时 axios 需设 `withCredentials: true`。
- 已开启 CORS：允许 `http://localhost:5173` 等本地前端跨域访问。

## 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/login` | body: `{role:'user'|'admin', username, password}` |
| POST/GET | `/api/logout` | 退出 |
| GET | `/api/me` | 当前登录用户 |

## 游客：演出浏览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/dicts` | 城市、类型字典 |
| GET | `/api/shows?city_id=&category_id=&keyword=` | 演出列表（含票价区间、show_dates 多场次日期、状态） |
| GET | `/api/shows/<id>` | 演出详情：show/summary/images/sessions/tiers（按场次分组） |

## 用户（需 role=user）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/buy` | 购票事务。body: `{show_id,session_id,tier_id,count,address_id,attendee_ids:[...]}` |
| GET | `/api/orders` | 我的订单（含每张票持票人） |
| GET | `/api/addresses` | 收货地址列表 |
| POST | `/api/addresses/add` | 新增：`{receiver_name,phone,address_detail,is_default}` |
| POST | `/api/addresses/update` | 修改：`{address_id,receiver_name,phone,address_detail,is_default}` |
| POST | `/api/addresses/default` | 设置默认：`{address_id}` |
| POST | `/api/addresses/delete` | 删除：`{address_id}` |
| GET | `/api/attendees` | 常用购票人列表 |
| POST | `/api/attendees/add` | 新增：`{attendee_name,id_type,id_no}` |
| POST | `/api/attendees/update` | 修改：`{attendee_id,attendee_name,id_type,id_no}` |
| POST | `/api/attendees/delete` | 删除：`{attendee_id}`（有订单则拒绝） |

## 管理员（需 role=admin）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/admin/shows` | 全部演出 + 城市/类型字典 |
| POST | `/api/admin/shows/create` | 新建演出 |
| GET | `/api/admin/shows/<id>` | 演出详情（含基本信息、介绍图片、该城市可选场馆、场次、票档） |
| POST | `/api/admin/shows/<id>/update` | 修改演出 |
| POST | `/api/admin/uploads/poster` | 上传演出海报（multipart 字段 `poster`，支持 JPG/PNG/GIF/WEBP，最大 5MB） |
| POST | `/api/admin/shows/<id>/delete` | 删除演出（有订单则拒绝，否则级联删场次/票档/图） |
| POST | `/api/admin/shows/<id>/images/add` | 添加介绍图片：`{image_url,sort_no}` |
| POST | `/api/admin/shows/<id>/images/<image_id>/delete` | 删除当前演出的介绍图片 |
| POST | `/api/admin/session/create` | 加场次：`{show_id,venue_id,show_time,sale_start}` |
| POST | `/api/admin/session/<id>/delete` | 删场次（级联票档；有订单则拒绝） |
| POST | `/api/admin/tier/create` | 加票档：`{session_id,tier_name,price,total_seats}` |
| POST | `/api/admin/tier/<id>/delete` | 删票档（有订单则拒绝） |
| GET | `/api/admin/stats?start=YYYY-MM-DD&end=YYYY-MM-DD` | 统计：daily 折线 / cats 饼图 / cities 柱图 / top TOP10 / total 指标 |

## 购票事务逻辑（与旧页面一致）

`/api/buy` 在单个数据库事务内完成：购票请求留痕 → 场次状态校验（预售/售罄拦截）→ 地址/购票人归属校验 →
每人每场次限购 1 张（应用层 + `UNIQUE(attendee_id,session_id)` 数据库唯一约束双保险）→
原子扣减余票（`UPDATE ... WHERE 总票-已售>=数量`，不超卖）→ 写订单 + 明细（单价快照）→
置为已支付（触发器累加 sales_daily）→ 请求置成功。任一步失败回滚并记录失败原因。
