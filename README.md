# 演出门票销售系统

这是一个基于 MySQL、Flask 和 Vue 3 的演出门票销售系统，面向数据库课程设计和本地演示场景。系统当前使用 Flask 提供 REST API，使用 Vue 3 + Vite 构建单页前端，生产构建产物由 Flask 从 `backend/static_web/` 托管。

系统支持游客浏览巡演和演出、用户登录购票、订单查询、收货信息和常用购票人管理，以及管理员的演出、场次、票档和销售统计管理。购票事务在后端和 MySQL 事务中执行，并记录成功或失败的购票请求。

> 当前唯一运行入口是 `http://127.0.0.1:5000/app/`。根路径 `/` 会自动重定向到该入口。旧版 Jinja2 页面已移除，当前只维护 Vue 3 前端和 Flask REST API。

## 功能概览

### 游客

- 浏览巡演/IP 列表，按城市、类型和关键词筛选。
- 查看巡演详情及其城市站点。
- 查看单场演出详情、演出图片、场次、场馆、票档、价格和余票。
- 访问登录页。

### 普通用户

- 使用演示账号登录。
- 选择场次、票档、票数、收货信息和购票人下单。
- 查看我的订单及订单明细。
- 新增、查看、删除收货信息。
- 新增、查看、删除常用购票人。

### 管理员

- 查看全部演出。
- 新建、编辑和删除演出，可选择本地图片上传海报，也可填写图片 URL。
- 为演出添加或删除场次。
- 为场次添加或删除票档。
- 按日期范围查看销售日趋势、类型、城市、热销演出和汇总指标。

### 数据库层约束

- 票档余票使用带条件的原子更新扣减，避免并发超卖。
- `order_item` 的唯一键 `UNIQUE(attendee_id, session_id)` 实现同一购票人同一场次限购 1 张。
- `purchase_request` 记录购票请求，包括失败原因。
- `ticket_order` 支付成功时由触发器累加 `sales_daily`。
- `show_session.sale_status` 表示预售中、售票中或售罄；数据库脚本包含状态推进事件定义。

## 技术栈与运行结构

| 层次 | 当前实现 |
| --- | --- |
| 数据库 | MySQL 8.0，InnoDB，utf8mb4，外键、CHECK、触发器、视图 |
| 后端 | Python 3.7+、Flask、PyMySQL |
| 前端 | Vue 3、Vite、Element Plus、Pinia、Vue Router、Axios、ECharts |
| 认证 | Flask Cookie Session；前端 Axios 使用 `withCredentials` |
| 生产托管 | Flask 将 `backend/static_web/` 作为 `/app/` 单页应用目录 |
| 开发代理 | Vite `5173` 将 `/api` 转发到 Flask `5000` |

请求关系如下：

```text
浏览器
  ├─ 生产模式: http://127.0.0.1:5000/app/ ──> Flask 静态文件 + /api
  └─ 开发模式: http://localhost:5173/app/ ──> Vite ──> Flask http://127.0.0.1:5000/api
                                              └──────> MySQL 127.0.0.1:3306
```

## 目录结构

```text
db_homework/
├─ backend/
│  ├─ app.py                 # Flask 应用入口、/、/app/ 路由和 CORS
│  ├─ config.py              # 数据库连接和 SECRET_KEY 配置
│  ├─ db.py                  # PyMySQL 连接、查询、写入和口令校验
│  ├─ api/                   # REST API 蓝图
│  │  ├─ auth.py             # 登录、退出、当前用户
│  │  ├─ shows.py            # 字典、巡演、演出列表和详情
│  │  ├─ orders.py           # 购票和订单
│  │  ├─ profile.py          # 收货信息和常用购票人
│  │  ├─ admin.py            # 管理员演出、场次和票档管理
│  │  └─ stats.py            # 管理员销售统计
│  ├─ static_web/            # 已构建的 Vue 前端，Flask 从 /app/ 托管
│  ├─ static/                # 新版仍使用的海报、艺人图片等媒体资源
│  └─ requirements.txt
├─ frontend/
│  ├─ src/                   # Vue 源码、路由、状态和页面
│  ├─ public/                # Vite 公共资源
│  ├─ package.json           # npm scripts 和前端依赖
│  ├─ package-lock.json
│  └─ vite.config.js         # /app/ base 和 /api 代理
├─ sql/
│  ├─ schema/                # ddl.sql、views.sql：表、约束、视图和触发器
│  ├─ seed/                  # seed_data.sql、phase4_seed_series.sql：基础/示例数据
│  ├─ migrations/            # phase4_series.sql：结构升级脚本
│  ├─ tests/                 # queries.sql、test_cases.sql：查询示例和数据库测试
│  └─ backups/               # 大型数据库备份，不参与初始化
├─ scripts/
│  ├─ data/                  # 数据生成、清洗、巡演聚合和媒体维护
│  ├─ tests/                 # API、数据一致性和状态分布测试
│  ├─ performance/           # 查询性能和 EXPLAIN 检查
│  └─ docs/                  # 课程设计文档生成辅助脚本
├─ test_tools/
│  ├─ ui_test.js             # Puppeteer UI 测试
│  ├─ shots/                 # UI 测试截图
│  └─ package.json
├─ docs/                     # API、部署、测试、数据库设计和课程报告
├─ .mysql/                   # 本机内置 MySQL 数据目录（若存在）
└─ start_website.bat         # Windows 唯一一键启动入口：MySQL + Flask
```

更完整的文件职责、修改边界和常用命令见 [`docs/项目结构说明.md`](docs/项目结构说明.md)。

## 环境要求

推荐在 Windows 上运行：

- Python 3.7 或更高版本。
- MySQL 8.0。`sql/schema/ddl.sql` 使用 `utf8mb4_0900_ai_ci`，不适用于 MySQL 5.7。
- Node.js 和 npm。只有需要修改 Vue 源码或运行 Vite 开发服务器时才需要。
- 可选：Navicat 或其他 MySQL 客户端，用于执行 SQL 和查看数据。

后端依赖位于 `backend/requirements.txt`：Flask 和 PyMySQL。前端依赖位于 `frontend/package.json`，以 `package-lock.json` 为准安装。

## 快速启动：已有数据库

如果本机的 `ticket_sales` 数据库已经存在，并且数据库连接配置正确：

### 方式 A：Windows 一键启动

双击项目根目录的 `start_website.bat`。脚本会：

1. 检查或启动项目附带的 MySQL 实例 `127.0.0.1:3306`。
2. 检查 `ticket_sales.show_item` 是否可查询。
3. 在 `backend/` 下运行 Flask。

启动后打开：

```text
http://127.0.0.1:5000/app/
```

脚本默认使用常见的 Windows MySQL 8.0 安装目录和系统 `python` 命令；换环境时不需要改源码，可在启动前通过 `MYSQLD`、`MYSQLADMIN`、`MYSQL`、`PY`、`DB_USER`、`DB_PASSWORD`、`DB_PORT` 以及 `DATA` 环境变量覆盖。项目维护脚本也统一读取 `backend/config.py`，数据库连接参数可用 `DB_HOST`、`DB_PORT`、`DB_USER`、`DB_PASSWORD`、`DB_NAME` 覆盖。

### 方式 B：命令行启动 Flask

先启动 MySQL，然后在项目根目录执行：

```powershell
cd backend
python -m pip install -r requirements.txt
python app.py
```

成功时终端会显示：

```text
Running on http://127.0.0.1:5000/
```

保持该终端窗口运行，再访问 `http://127.0.0.1:5000/app/`。关闭 Flask 进程后网站不可访问，但不会自动删除数据库数据。

## 首次建库和导入演示数据

`ddl.sql` 会执行 `DROP DATABASE IF EXISTS ticket_sales`，因此只适合初始化或明确重置数据库时使用。执行前请备份需要保留的数据。

使用 Navicat、MySQL Workbench 或 `mysql` 客户端按以下顺序执行：

```text
sql/schema/ddl.sql
sql/seed/seed_data.sql
```

使用命令行时，示例为：

```powershell
mysql -h 127.0.0.1 -P 3306 -u root -p < sql/schema/ddl.sql
mysql -h 127.0.0.1 -P 3306 -u root -p < sql/seed/seed_data.sql
```

检查数据库：

```sql
SELECT COUNT(*) FROM ticket_sales.show_item;
SELECT COUNT(*) FROM ticket_sales.show_session;
SELECT COUNT(*) FROM ticket_sales.ticket_order;
```

当前仓库中的数据库可能已经由数据生成脚本扩充，数量不一定等于基础 seed 数据的数量。`sql/schema/views.sql` 通常不需要单独执行，因为 `ddl.sql` 已包含 3 个业务视图；如果视图被删除或需要单独重建，再执行该文件。

### 数据库连接配置

默认配置在 `backend/config.py`：

```python
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': '<your-mysql-password>',
    'database': 'ticket_sales',
    'charset': 'utf8mb4',
}
```

可用环境变量覆盖连接参数：`DB_HOST`、`DB_PORT`、`DB_USER`、`DB_PASSWORD`、`DB_NAME`。例如：

```powershell
$env:DB_PASSWORD = 'your-mysql-password'
python backend/app.py
```

请勿把真实生产密码提交到 Git。`config.py` 和 `start_website.bat` 默认不设置密码；如果 MySQL 需要密码，请在启动前设置 `DB_PASSWORD` 环境变量。

## 前端开发模式

开发模式需要同时运行 Flask 和 Vite，适合修改 `frontend/src/` 后热更新。

终端 1，启动后端：

```powershell
cd backend
python -m pip install -r requirements.txt
python app.py
```

终端 2，启动 Vite：

```powershell
cd frontend
npm install
npm run dev
```

访问 Vite 显示的地址，通常是：

```text
http://localhost:5173/app/
```

`frontend/vite.config.js` 已配置 `/api` 到 `http://127.0.0.1:5000` 的代理。不要在开发模式下直接双击 `frontend/index.html`，因为 Vue 模块、路由和 API 代理需要由 Vite 提供。

常用前端命令：

```powershell
npm run dev      # Vite 开发服务器
npm run build    # 构建到 frontend/dist
npm run preview  # 本地预览构建产物
```

## 生产构建和部署

当前仓库已经包含一份 `backend/static_web/` 构建产物。修改前端源码后，需要重新构建并同步产物：

```powershell
cd frontend
npm install
npm run build
```

然后将 `frontend/dist/` 下的文件复制到 `backend/static_web/`，保留 `assets/` 子目录。例如 PowerShell：

```powershell
Copy-Item -Recurse -Force .\dist\* ..\backend\static_web\
```

重新启动 Flask 后访问：

```text
http://127.0.0.1:5000/app/
```

`backend/app.py` 会把 `/app/` 和 `/app/<path>` 映射到 `backend/static_web/`，未知的前端路径会回退到 `index.html`，适配 Vue Hash 路由。

## 前端页面和路由

前端使用 Hash 路由，页面路径位于 `/app/#/` 后：

| 路径 | 页面 | 权限 |
| --- | --- | --- |
| `#/series` | 巡演/IP 列表 | 游客可访问 |
| `#/series/:id` | 巡演详情及城市站点 | 游客可访问 |
| `#/shows` | 演出列表 | 游客可访问 |
| `#/shows/:id` | 演出详情和购票 | 详情游客可看，购票需用户登录 |
| `#/login` | 登录 | 游客可访问 |
| `#/orders` | 我的订单 | 普通用户 |
| `#/addresses` | 收货信息 | 普通用户 |
| `#/attendees` | 常用购票人 | 普通用户 |
| `#/admin/shows` | 演出管理 | 管理员 |
| `#/admin/shows/:id` | 场次和票档编辑 | 管理员 |
| `#/admin/stats` | 销售统计 | 管理员 |

## REST API 摘要

基础地址：`http://127.0.0.1:5000/api`。成功响应通常为 `{ "code": 0, "msg": "ok", "data": ... }`；未登录为 `401`，无权限为 `403`，其他业务错误由 `msg` 说明。完整字段和请求示例见 [`docs/API接口说明.md`](docs/API接口说明.md)。

| 模块 | 方法和路径 |
| --- | --- |
| 认证 | `POST /login`、`POST/GET /logout`、`GET /me` |
| 字典和浏览 | `GET /dicts`、`GET /series`、`GET /series/<id>`、`GET /shows`、`GET /shows/<id>` |
| 用户购票 | `POST /buy`、`GET /orders` |
| 用户资料 | `GET /addresses`、`POST /addresses/add`、`POST /addresses/delete`、`GET /attendees`、`POST /attendees/add`、`POST /attendees/delete` |
| 管理员演出 | `GET /admin/shows`、`POST /admin/shows/create`、`GET/POST /admin/shows/<id>`、`POST /admin/shows/<id>/delete` |
| 管理员场次和票档 | `POST /admin/session/create`、`POST /admin/session/<id>/delete`、`POST /admin/tier/create`、`POST /admin/tier/<id>/delete` |
| 管理员统计 | `GET /admin/stats?start=YYYY-MM-DD&end=YYYY-MM-DD` |

购票接口的核心请求字段为 `show_id`、`session_id`、`tier_id`、`count`、`address_id` 和 `attendee_ids`。后端会校验登录角色、场次状态、地址和购票人归属、票数与购票人数量、每人每场限购和剩余票数；失败请求也会写入 `purchase_request`。

## 演示账号

基础 seed 数据中的演示账号密码统一为 `123456`：

| 角色 | 账号 |
| --- | --- |
| 普通用户 | `zhang_san`、`li_si`、`wang_wu`、`zhao_liu`、`chen_qi` |
| 管理员 | `admin` |

批量生成脚本还会创建以 `u...` 或 `f...` 开头的用户；这些账号使用数据库中的演示占位哈希，后端会按演示口令 `123456` 校验。

## 数据库脚本说明

| 文件 | 用途 | 是否会破坏现有数据 |
| --- | --- | --- |
| `sql/schema/ddl.sql` | 重建数据库、表、视图、触发器和约束 | 是，删除并重建 `ticket_sales` |
| `sql/seed/seed_data.sql` | 清空业务表后导入基础演示数据 | 是，会清空已有业务数据 |
| `sql/schema/views.sql` | 独立创建业务视图 | 仅修改视图 |
| `sql/tests/queries.sql` | 常用查询、购票事务和统计 SQL 示例 | 视语句而定，默认不建议直接全量执行 |
| `sql/tests/test_cases.sql` | 约束、触发器、购票和统计测试 | 含写入、失败用例和清理语句，执行前阅读 |
| `sql/migrations/phase4_series.sql` | 巡演/IP 结构升级 | 取决于脚本内容，执行前备份 |
| `sql/seed/phase4_seed_series.sql` | 巡演/IP 示例数据 | 会写入巡演相关数据 |

数据库当前包含城市、类型、管理员、用户、场馆、巡演、演出、图片、场次、票档、收货信息、购票人、订单、订单明细、购票请求和销售日汇总等表；具体字段和外键以 `sql/schema/ddl.sql` 为准。

## 数据生成和性能测试

这些脚本从各自分类目录运行，并从 `backend/config.py` 读取数据库连接配置。推荐从项目根目录用完整路径调用。

### 中等演示数据

```powershell
python scripts/data/gen_more_data.py
```

脚本会清理自己生成的批量数据（订单号以 `B` 开头、批量用户和 `show_id > 8` 的演出），保留基础演示账号和核心演出，然后生成额外城市、场馆、演出、用户、历史订单和购票请求。重复运行会重建该批数据。

### 大规模数据

```powershell
python scripts/data/gen_full_scale.py
```

脚本面向性能实验，会生成约 100 个城市、10 万用户、约 1000 个场次和约 100 万张历史售票数据。数据量大、执行时间长，并会显著增加数据库文件大小；只应在专用测试库执行。

### 性能检查

```powershell
python scripts/performance/perf_check.py
```

脚本检查登录、列表、详情、订单和统计查询，并输出耗时及 `EXPLAIN` 结果。性能数字依赖机器、数据规模和 MySQL 配置，不能直接当作生产基准。

## 测试

### API 测试

确保 MySQL 和 Flask 已启动后，在项目根目录运行：

```powershell
python scripts/tests/test_api.py
```

测试结果会写入 `docs/test-results/test_api_results.json`。脚本可能创建测试订单或测试数据，执行前请阅读脚本中的清理逻辑。

### 浏览器 UI 测试

`test_tools/` 使用 Puppeteer Core：

```powershell
cd test_tools
npm install
node ui_test.js
```

测试前需要先启动网站。截图和 JSON 结果默认保存在 `test_tools/shots/`、`test_tools/ui_results.json` 等文件中。

### SQL 测试

在测试数据库中阅读并执行 `sql/tests/test_cases.sql`。该文件包含购票事务、不超卖、限购、触发器、状态和 CHECK 约束验证，其中部分用例故意执行失败语句来确认数据库拒绝非法数据。

项目中的测试文档和实测报告位于 `docs/`，包括 [`docs/系统功能测试手册.md`](docs/系统功能测试手册.md)、[`docs/新版功能测试说明书_实测填写版.md`](docs/新版功能测试说明书_实测填写版.md) 和 [`docs/功能测试执行报告.md`](docs/功能测试执行报告.md)。

## 常见问题

### 浏览器提示无法连接 `127.0.0.1:5000`

确认 Flask 终端仍在运行，并检查端口：

```powershell
Get-NetTCPConnection -LocalPort 5000 -State Listen
```

然后访问 `http://127.0.0.1:5000/app/`。如果端口被其他程序占用，需要停止占用进程，或修改 `backend/app.py` 的端口并同步修改前端 Vite 代理。

### 页面打开但空白或资源 404

- 生产模式检查 `backend/static_web/index.html` 和 `backend/static_web/assets/` 是否完整。
- 修改前端后重新运行 `npm run build`，再将 `frontend/dist/` 内容复制到 `backend/static_web/`。
- 不要把生产 `/app/` 地址和 Vite 开发地址混用。

### API 返回 `401` 或页面提示请先登录

登录态保存在浏览器 Cookie Session 中。确认浏览器没有禁用 Cookie，并使用同一个主机名访问前端和后端，例如都使用 `127.0.0.1`，不要在 `localhost` 和 `127.0.0.1` 之间切换。

### API 报 MySQL 连接失败

检查 MySQL 是否监听 `3306`、`backend/config.py` 或环境变量中的账号密码是否正确，以及 `ticket_sales` 数据库是否已经执行 `ddl.sql` 和 `seed_data.sql`。

### `Unknown collation utf8mb4_0900_ai_ci`

项目 SQL 针对 MySQL 8.0。MySQL 5.7 不支持该排序规则，请使用 MySQL 8.0，或在确认兼容性后自行修改 SQL 排序规则。

### 执行 `ddl.sql` 或 `seed_data.sql` 后数据消失

这是脚本的预期行为：`ddl.sql` 会删除并重建数据库，`seed_data.sql` 会清空业务表后重新插入基础数据。生产或重要测试库执行前必须备份。

## 已知限制

- 当前账号体系主要用于课程演示，没有注册、找回密码、支付网关和真实短信验证流程。
- 当前后端使用 Flask 内置开发服务器，不应直接用于公网生产部署。
- 一键启动脚本仍以 Windows 本地演示为目标；如果 MySQL 需要密码，请通过环境变量设置 `DB_PASSWORD`。跨平台运行请使用命令行方式。
- 前端当前使用 Hash 路由，页面链接形如 `/app/#/shows`。
- 旧版 Jinja2 模板和旧版 Flask 页面已从当前工作目录移除；`backend/app.py` 只注册 REST API 和 Vue 静态托管路由。
- `backend/static_web/` 是构建产物，不会随 `npm run build` 自动同步到后端目录。

## 相关文档

- [API 接口说明](docs/API接口说明.md)
- [组员部署使用手册](docs/组员部署使用手册.md)
- [系统功能测试手册](docs/系统功能测试手册.md)
- [新版功能测试说明书（实测填写版）](docs/新版功能测试说明书_实测填写版.md)
- [功能测试执行报告](docs/功能测试执行报告.md)
- [数据库设计](docs/演出门票销售系统_数据库设计.md)
- [前端说明](frontend/README.md)

## 来源与核对日期

本 README 的项目事实以当前仓库源码、SQL、脚本和文档为准；框架命令和运行概念参考官方文档：

- [Flask Quickstart](https://flask.palletsprojects.com/en/stable/quickstart/) — Pallets Projects。
- [Vue.js Quick Start](https://vuejs.org/guide/quick-start.html) — Vue 官方文档。
- [Vite Guide](https://vite.dev/guide/) — Vite 官方文档。
- [MySQL 8.0 Reference Manual](https://dev.mysql.com/doc/refman/8.0/en/) — Oracle MySQL 官方文档。

资料核对日期：2026-10-02。
