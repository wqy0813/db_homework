# 演出门票销售系统分域数据库模型

为减少交叉，概念模型和逻辑模型均按业务域拆分。跨图重复出现的实体只是为了表达跨域关系，数据库中仍然只有一张表。

## 概念模型

### 1. 演出基础信息

```mermaid
flowchart LR
  CITY[城市] ---|1:N 位于| VENUE[场馆]
  CITY ---|1:N 举办| SHOW[演出]
  CATEGORY[演出类型] ---|1:N 分类| SHOW
  ADMIN[管理员] ---|1:N 创建| SHOW
  SHOW ---|1:N 安排| SESSION[演出场次]
  VENUE ---|1:N 承办| SESSION
  SESSION ---|1:N 设置| TIER[票档]
```

### 2. 用户资料

```mermaid
flowchart LR
  USER[用户] ---|1:N 保存| ADDRESS[收货信息]
  USER ---|1:N 维护| ATTENDEE[常用购票人]
```

### 3. 订单与购票

```mermaid
flowchart LR
  USER[用户] ---|1:N 提交| ORDER[订单]
  ADDRESS[收货信息] ---|1:N 使用地址| ORDER
  SESSION[演出场次] ---|1:N 对应场次| ORDER
  TIER[票档] ---|1:N 选择票档| ORDER
  ORDER ---|1:1..N 包含| ITEM[订单明细]
  ATTENDEE[常用购票人] ---|1:N 持有| ITEM
```

### 4. 请求与统计

```mermaid
flowchart LR
  USER[用户] ---|1:N 记录| REQUEST[购票请求]
  SESSION[演出场次] ---|1:N 针对| REQUEST
  TIER[票档] ---|1:N 请求票档| REQUEST
  ORDER[订单] -.->|支付成功后汇总| DAILY[销售统计]
```

游客是访问角色，不单独作为数据库实体。

## 逻辑模型

### 1. 演出基础表

```mermaid
erDiagram
  CITY ||--o{ VENUE : contains
  CITY ||--o{ SHOW : locates
  CATEGORY ||--o{ SHOW : classifies
  ADMIN ||--o{ SHOW : creates
  SHOW ||--o{ SHOW_SESSION : schedules
  VENUE ||--o{ SHOW_SESSION : hosts
  SHOW_SESSION ||--o{ TICKET_TIER : offers
```

字段级主外键映射：

- `VENUE.city_id` → `CITY.city_id`
- `SHOW.category_id` → `CATEGORY.category_id`
- `SHOW.city_id` → `CITY.city_id`
- `SHOW.admin_id` → `ADMIN.admin_id`
- `SHOW_SESSION.show_id` → `SHOW.show_id`
- `SHOW_SESSION.venue_id` → `VENUE.venue_id`
- `TICKET_TIER.session_id` → `SHOW_SESSION.session_id`

### 2. 用户资料表

```mermaid
erDiagram
  APP_USER ||--o{ SHIPPING_ADDRESS : saves
  APP_USER ||--o{ ATTENDEE : maintains
```

字段级主外键映射：

- `SHIPPING_ADDRESS.user_id` → `APP_USER.user_id`
- `ATTENDEE.user_id` → `APP_USER.user_id`

### 3. 订单交易表

```mermaid
erDiagram
  APP_USER ||--o{ TICKET_ORDER : places
  SHIPPING_ADDRESS ||--o{ TICKET_ORDER : uses
  SHOW_SESSION ||--o{ TICKET_ORDER : targets
  TICKET_TIER ||--o{ TICKET_ORDER : prices
  TICKET_ORDER ||--|{ ORDER_ITEM : contains
  ATTENDEE ||--o{ ORDER_ITEM : holds
```

字段级主外键映射：

- `TICKET_ORDER.user_id` → `APP_USER.user_id`
- `TICKET_ORDER.session_id` → `SHOW_SESSION.session_id`
- `TICKET_ORDER.tier_id` → `TICKET_TIER.tier_id`
- `TICKET_ORDER.address_id` → `SHIPPING_ADDRESS.address_id`
- `ORDER_ITEM.order_id` → `TICKET_ORDER.order_id`
- `ORDER_ITEM.attendee_id` → `ATTENDEE.attendee_id`

一致性约束：`TICKET_ORDER(session_id, tier_id)` 与 `TICKET_TIER(session_id, tier_id)` 成对对应。

### 4. 请求与统计表

```mermaid
erDiagram
  APP_USER ||--o{ PURCHASE_REQUEST : records
  SHOW_SESSION ||--o{ PURCHASE_REQUEST : concerns
  TICKET_TIER ||--o{ PURCHASE_REQUEST : requests
  TICKET_ORDER ||..o{ SALES_DAILY : derives
```

说明：`PURCHASE_REQUEST.user_id`、`PURCHASE_REQUEST.session_id`、`PURCHASE_REQUEST.tier_id` 作为请求上下文记录，当前基础 DDL 未声明为物理外键；`SALES_DAILY` 为订单汇总得到的派生表。
