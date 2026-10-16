# 后端 REST API 接口说明

Flask 后端提供 `/api/*` JSON 接口供 Vue 前端调用；页面由 Vue 单页应用托管，根路径 `/` 重定向到 `/app/`。
- **基础地址**：`http://127.0.0.1:5000/api`
- **统一响应格式**：`{ "code": 0, "msg": "ok", "data": {...} }`
  - `code = 0`：操作成功；
  - `code = 401`：未登录；
  - `code = 403`：权限不足（如普通用户访问管理端）；
  - `code = 1`（或其他非 0 值）：业务校验失败，失败原因在 `msg` 中明确提示用户。
- **登录凭证**：基于 Cookie Session（登录后自动在响应中下发 `session` cookie，前端发请求需携带 `withCredentials: true`）。
- **跨域支持**：后端已集成 CORS，允许本地 Vite 开发服务（`http://localhost:5173` 等）跨域访问。

---

## 演出与场次销售状态标准对照

系统所有页面和后端统一遵循以下四态定义：

| 状态码 (`sale_status` / `show_status`) | 状态名称 | 判定规则 | 业务说明 |
|:---:|:---:|:---|:---|
| **1** | **预售中** | `show_time > NOW() AND sale_start > NOW() AND 余票 > 0` | 尚未到开售时间，用户可提前浏览并维护观演人/地址资料，禁止提交购票。 |
| **2** | **售票中** | `show_time > NOW() AND sale_start <= NOW() AND 余票 > 0` | 处于开放购票窗口期且尚有余票，允许正常下单支付。 |
| **3** | **售罄** | `show_time > NOW() AND 余票 <= 0` | 未来场次但所有票档余票均已售完，不可再购买。 |
| **4** | **已结束** | `show_time <= NOW()` | 开演时间已过，场次关闭。 |

### 状态自动推进机制
1. **数据库调度事件 (`ev_session_status`)**：MySQL 8.0 Event Scheduler 每 1 分钟自动执行一次全表扫描推进状态。
2. **应用层即时触发 (`refresh_sale_statuses`)**：每次调用演出列表、详情、巡演或购票接口时，系统自动检查并同步当前演出的最新状态，保证无延迟生效。

---

## 一、用户认证与注册

### 1.1 用户登录
- **方法/路径**：`POST /api/login`
- **请求体**：
  ```json
  {
    "role": "user", // "user" 或 "admin"
    "username": "zhang_san",
    "password": "your_password"
  }
  ```
- **成功返回**：`{ "code": 0, "msg": "登录成功", "data": { "user": { "id": 1, "name": "zhang_san", "role": "user" } } }`
- **失败返回**：`{ "code": 1, "msg": "登录失败：用户名或密码错误" }`

### 1.2 退出登录
- **方法/路径**：`POST /api/logout` 或 `GET /api/logout`
- **成功返回**：`{ "code": 0, "msg": "已退出" }`

### 1.3 获取当前登录态
- **方法/路径**：`GET /api/me`
- **成功返回**：`{ "code": 0, "data": { "user": { "id": 1, "name": "zhang_san", "role": "user" } } }`（未登录返回 401）

### 1.4 新用户注册
- **方法/路径**：`POST /api/register`
- **说明**：仅允许注册普通用户（`role='user'`），系统绝不通过注册接口创建管理员。
- **请求体**：
  ```json
  {
    "username": "new_user",
    "password": "password123",
    "confirm_password": "password123",
    "phone": "13912345678",
    "email": "user@example.com" // 可选
  }
  ```
- **字段规则**：
  - `username`：必填，2~50 字符，仅限中文、字母、数字或下划线；不可与已有用户重名。
  - `password`：必填，6~64 字符。
  - `confirm_password`：必填，必须与 `password` 一致。
  - `phone`：必填，11 位数字以 1 开头；不可重复注册。
  - `email`：选填，若填写必须符合邮箱格式。
- **成功返回**：`{ "code": 0, "msg": "注册成功，请登录", "data": { "user_id": 123 } }`
- **失败返回**：`{ "code": 1, "msg": "用户名已被注册，请更换" }` 等明确错误。

---

## 二、演出与巡演浏览（游客/用户公开接口）

### 2.1 基础字典
- **方法/路径**：`GET /api/dicts`
- **说明**：获取所有可用城市及演出分类。
- **返回示例**：`{ "code": 0, "data": { "cities": [...], "categories": [...] } }`

### 2.2 巡演列表（首页聚合展示）
- **方法/路径**：`GET /api/series`
- **请求参数**：
  - `city_id`：城市 ID（可选）
  - `category_id`：分类 ID（可选）
  - `status`：销售状态 1~4（可选）
  - `keyword`：巡演名称或主要艺人关键词（可选）
- **返回示例**：
  ```json
  {
    "code": 0,
    "data": {
      "list": [
        {
          "series_id": 1,
          "series_name": "周杰伦《嘉年华》世界巡回演唱会",
          "main_artist": "周杰伦",
          "poster_url": "/posters/D/series_069_poster.jpg",
          "category_id": 1,
          "category_name": "演唱会",
          "station_count": 6,
          "city_count": 6,
          "min_price": 380.0,
          "max_price": 1980.0,
          "show_dates": "10.20 / 11.15",
          "status": 2
        }
      ]
    }
  }
  ```

### 2.3 巡演详情及站点列表
- **方法/路径**：`GET /api/series/<series_id>`
- **说明**：查看巡演整体信息与下属各城市站及场次状态。
- **返回示例**：
  ```json
  {
    "code": 0,
    "data": {
      "series": { "series_id": 1, "series_name": "...", "main_artist": "..." },
      "stations": [
        {
          "show_id": 1,
          "city_id": 1,
          "city_name": "北京",
          "min_price": 380.0,
          "max_price": 1980.0,
          "session_count": 2,
          "show_status": 2,
          "show_dates": "10.20 / 12.14"
        }
      ]
    }
  }
  ```

### 2.4 演出列表（城市站单体列表）
- **方法/路径**：`GET /api/shows`
- **请求参数**：`city_id`, `category_id`, `status`, `keyword`

### 2.5 演出单站详情（购票页面数据源）
- **方法/路径**：`GET /api/shows/<show_id>`
- **返回**：包含 `show` 基本信息、`sessions`（场次列表，含场馆、开演开售时间、场次状态）、`tiers`（按 `session_id` 分组的票档，含原价、总票数、已售、余票）、`images`（兼容字段，固定为空列表；额外介绍图片功能已移除）。

---

## 三、用户端：购票、订单与资料维护（需普通用户登录）

### 3.1 核心购票事务
- **方法/路径**：`POST /api/buy`
- **说明**：单笔订单支持购买 1~6 张票；单笔订单持票人数量必须等于票数；每位观演人同一场次严格限购 1 张（数据库唯一索引 + 排他锁双重保证）。
- **请求体**：
  ```json
  {
    "show_id": 1,
    "session_id": 1,
    "tier_id": 3,
    "count": 2,
    "address_id": 1,
    "attendee_ids": [101, 102]
  }
  ```
- **核心业务校验拦截**：
  - 未开售场次拦截并提示：`演出尚未开售（预售中）`；
  - 售罄场次/票档拦截并提示：`该场次已售罄` 或 `余票不足：该票档剩余票数不足`；
  - 超出限购拦截：`超出限购：购票人【XXX】已购买该场次门票（每人限购 1 张）`；
  - 购票人数量不一致拦截：`购票人数量必须与票数一致（每人限购 1 张）`。
- **成功返回**：`{ "code": 0, "msg": "购票成功！...", "data": { "order_no": "NO...", "order_id": 123 } }`

### 3.2 我的订单列表（分页与搜索）
- **方法/路径**：`GET /api/orders`
- **请求参数**：
  - `page`：当前页码，从 1 开始，默认 1。
  - `page_size`：每页条数，支持 10、20、50，默认 10。
  - `keyword`：可选，按订单号或演出名称模糊搜索。
- **说明**：后端按页码和页大小切分，列表仅返回订单展示核心字段。
- **返回示例**：
  ```json
  {
    "code": 0,
    "data": {
      "page": 1,
      "page_size": 10,
      "total": 35,
      "list": [
        {
          "order_id": 101,
          "order_no": "NO20261015001",
          "show_name": "周杰伦《嘉年华》世界巡回演唱会·北京站",
          "city_name": "北京",
          "venue_name": "国家体育场（鸟巢）",
          "show_time": "2026-10-20 19:30:00",
          "ticket_count": 2,
          "total_amount": 1160.00,
          "order_status": 2,
          "create_time": "2026-10-15 11:30:00",
          "pay_time": "2026-10-15 11:30:05"
        }
      ]
    }
  }
  ```

### 3.3 订单详情查询
- **方法/路径**：`GET /api/orders/<order_id>`
- **说明**：返回该笔订单的完整明细，包括票档单价、收货人地址信息及脱敏后的持票人证件号码。
- **返回示例**：
  ```json
  {
    "code": 0,
    "data": {
      "order_id": 101,
      "order_no": "NO20261015001",
      "order_status": 2,
      "show_name": "周杰伦《嘉年华》世界巡回演唱会·北京站",
      "show_time": "2026-10-20 19:30:00",
      "city_name": "北京",
      "venue_name": "国家体育场（鸟巢）",
      "tier_name": "看台 580",
      "tier_price": 580.00,
      "ticket_count": 2,
      "total_amount": 1160.00,
      "receiver_name": "张三",
      "phone": "13800000001",
      "address_detail": "北京市海淀区中关村大街1号",
      "create_time": "2026-10-15 11:30:00",
      "pay_time": "2026-10-15 11:30:05",
      "items": [
        {
          "attendee_name": "张三",
          "id_type": 1,
          "masked_id_no": "**************1234",
          "unit_price": 580.00
        }
      ]
    }
  }
  ```

### 3.4 收货地址管理
- `GET /api/addresses`：获取当前用户地址列表。
- `POST /api/addresses/add`：新增地址 `{ receiver_name, phone, address_detail, is_default }`。
- `POST /api/addresses/update`：修改地址 `{ address_id, receiver_name, phone, address_detail, is_default }`。
  - **重要保护规则**：若该地址已被历史订单引用，系统拒绝修改或删除，并明确提示：“为保留历史订单信息，不能修改或删除，可以新增一条用于后续购票。”
- `POST /api/addresses/default`：设为默认地址 `{ address_id }`。
- `POST /api/addresses/delete`：删除地址 `{ address_id }`（已被历史订单引用的地址会被拒绝）。

### 3.5 常用观演人管理
- `GET /api/attendees`：获取常用观演人列表。
- `POST /api/attendees/add`：新增观演人 `{ attendee_name, id_type, id_no }`。
- `POST /api/attendees/update`：修改观演人 `{ attendee_id, attendee_name, id_type, id_no }`。
  - **重要保护规则**：已被历史订单引用的观演人拒绝修改或删除，并提示：“该购票人已被订单引用，为保留历史订单不可删除，可以新增一位用于后续购票。”
- `POST /api/attendees/delete`：删除观演人 `{ attendee_id }`。

---

## 四、管理员端接口（需管理员登录 `role='admin'`）

### 4.1 演出管理
- `GET /api/admin/shows`：管理员演出列表及检索。
- `POST /api/admin/shows/create`：新建单场演出。
- `GET /api/admin/shows/<id>`：获取演出详情、已有关联场次、票档及所属城市场馆。
- `POST /api/admin/shows/<id>/update`：修改演出基本信息（名称、分类、城市、海报、简介）。
- `POST /api/admin/shows/<id>/delete`：删除演出（如果该演出下已有历史订单，系统将拒绝删除：“删除失败：该演出已有订单，为保留销售数据不可删除”）。
- `POST /api/admin/uploads/poster`：上传主海报文件（图片格式，最大 5MB）。

### 4.2 场次管理（新增与修改）
- **新建场次**：`POST /api/admin/session/create`
  - **参数**：`{ show_id, venue_id, show_time, sale_start }`
  - **规则**：`show_time` 不能早于当前时间；`sale_start` 默认或根据规则校验；场馆必须为演出同城场馆。
- **编辑场次**：`POST /api/admin/session/<session_id>/update`
  - **参数**：`{ show_id, venue_id, show_time, sale_start }`
  - **规则**：
    - 若该场次**已有订单**：**严禁修改场馆与开演时间**，接口直接拒绝并提示原因；
    - 若该场次**尚无订单**：允许调整场馆与开演时间，但新的场馆容量必须 `>=` 当前场次所有票档总票数之和。
- **删除场次**：`POST /api/admin/session/<session_id>/delete`
  - 若已有订单则拒绝删除；无订单时级联删除场次及对应票档。

### 4.3 票档管理（新增与修改）
- **新建票档**：`POST /api/admin/tier/create`
  - **参数**：`{ session_id, tier_name, price, total_seats }`
  - **容量控制规则**：系统使用排他锁校验 `SUM(total_seats) + 新增 total_seats <= 场馆容量`。若超出则明确拒绝并返回：`票档总票数(X张)超过场馆容量(Y座)`。
- **编辑票档**：`POST /api/admin/tier/<tier_id>/update`
  - **参数**：`{ session_id, tier_name, price, total_seats }`
  - **规则**：
    - 若该票档**已有订单**（`sold_seats > 0`）：**禁止修改票档名称**（保持历史订单票档语义），但**允许修改后续售价与总票数**；
    - 新的 `total_seats` 必须 `>= sold_seats`（不能改得低于已售出票数）；
    - 所有票档更新后的总票数之和不能超过场馆容量；
    - 旧订单价格不受影响（订单明细表已对购买单价留存快照）。
- **删除票档**：`POST /api/admin/tier/<tier_id>/delete`
  - 若已售票数 `sold_seats > 0` 或存在关联订单则拒绝删除。

### 4.4 巡演与站点聚合管理
- `GET /api/admin/series`：巡演列表及检索。
- `POST /api/admin/series/create`：新建巡演系列。
- `GET /api/admin/series/<id>`：获取巡演及下属所有站点。
- `POST /api/admin/series/<id>/update`：编辑巡演。
- `POST /api/admin/series/<id>/delete`：删除巡演系列。
- `POST /api/admin/series/<id>/stations/add`：关联已有演出站点到巡演系列。
- `POST /api/admin/series/<id>/stations/<show_id>/remove`：从巡演中移除站点。

### 4.5 销售统计看板
- **方法/路径**：`GET /api/admin/stats`
- **请求参数**：`start=YYYY-MM-DD&end=YYYY-MM-DD`（支持跨度查询）
- **返回数据**：
  - `total`：区间内订单总数、已售票数、销售总金额指标卡；
  - `daily`：每日销售趋势折线图数据（日期、票数、金额）；
  - `cats`：各演出类型销售占比饼图数据；
  - `cities`：各城市售票分布柱状图数据；
  - `top`：销量最高的 TOP 10 演出排行。
