# 演出门票销售系统（数据库课程设计）

一个完整的**演出门票在线销售系统**：关系数据库设计 + 可运行的 Web 演示系统（Flask + MySQL 8.0）。
支持游客、用户、管理员三种角色，覆盖登录、演出浏览、购票下单（不超卖/每人限购 1 张/购票请求留痕）、
订单管理、收货信息与常用购票人维护、演出管理、按时间段销售统计（ECharts 图表）等功能。

## 技术栈

- 数据库：**MySQL 8.0**（InnoDB、事务、外键、CHECK、触发器、事件、索引/分区方案）
- 后端：**Python + Flask + PyMySQL**
- 前端：Jinja2 服务端渲染 + 原生 CSS + **ECharts 5**（本地化，离线可渲染）

## 目录结构

```
├─ 演出门票销售系统_数据库设计.md   # 设计主文档：需求分析→概念设计(E-R)→逻辑设计→物理设计
├─ 演出门票销售系统_课程设计报告.docx
├─ ddl.sql                  # 建库建表 + 视图（必跑）
├─ seed_data.sql            # 基础测试数据（8 场演出、账号等，必跑）
├─ views.sql                # 3 个业务视图（新版 ddl 已内置）
├─ queries.sql              # 典型业务 SQL 与统计查询
├─ test_cases.sql           # 43 个可直接运行的测试用例 SQL
├─ gen_more_data.py         # （可选）生成中等规模演示数据
├─ gen_full_scale.py        # （可选）满规模压测数据：10万用户/约1000场次/约100万张票
├─ perf_check.py            # （可选）性能实测与索引命中验证
├─ app/                     # Web 系统
│   ├─ app.py / config.py / run.bat / requirements.txt
│   ├─ templates/  static/
│   └─ README.md
├─ 组员部署使用手册.md        # 在自己电脑上运行系统的步骤
├─ 系统功能测试手册.md        # 每个功能的逐条测试清单
├─ Navicat操作说明.md
└─ 测试说明书.md
```

## 快速开始（3 步）

1. 安装 **MySQL 8.0** 与 **Python 3.7+**；
2. 用 Navicat 依次运行 `ddl.sql`、`seed_data.sql`，然后把 `app/config.py` 里的密码改成你自己的 MySQL 密码；
3. 双击 `app/run.bat`（或 `pip install -r app/requirements.txt && python app/app.py`），
   浏览器打开 <http://127.0.0.1:5000>。

**演示账号**：用户 `zhang_san` / 管理员 `admin`，密码均为 `123456`。

详细步骤见 [组员部署使用手册.md](组员部署使用手册.md)，功能测试见 [系统功能测试手册.md](系统功能测试手册.md)。

## 数据规模与性能

- 支持题目要求的大数据量：约 10 万用户、每年约 1000 场次、场均 5000 座、约 100 城市；
- 用 `gen_full_scale.py` 灌入实测数据（100 城 / 10 万用户 / 1078 场次 / 约 100 万张票）后，
  登录、列表筛选、下单扣票、我的订单等在线操作**毫秒级**，跨年度统计**秒级**，
  `EXPLAIN` 显示关键查询全部命中索引；超卖 0、限购重复 0。

## 数据库设计要点

- 不超卖：`UPDATE ticket_tier SET sold_seats=sold_seats+n WHERE tier_id=? AND total_seats-sold_seats>=n`
  原子扣减 + InnoDB 行锁 + CHECK 兜底；
- 每人每场限购 1 张：`order_item` 上 `UNIQUE(attendee_id, session_id)`；
- 所有购票请求（含失败及原因）写入 `purchase_request` 留痕；
- 统计加速：支付触发器累加 `sales_daily` 日汇总表；
- 状态自动推进：事件 `ev_session_status` 每 10 分钟推进"预售中→售票中→售罄"。
