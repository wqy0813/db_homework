-- ============================================================================
-- 演出门票销售系统 物理建库脚本 (MySQL 8.0 / InnoDB / utf8mb4)
-- 对应文档：《演出门票销售系统_数据库设计.md》第四部分
-- 说明：
--   1) 本脚本为「非分区版本」，全部主外键完整，便于课程演示参照完整性；
--   2) 文件末尾附「大数据量分区改造」片段，面向 5 年以上增长的工程化选择
--      （MySQL 分区表不支持外键，分区版需去掉相应外键、由应用层保证参照完整性）；
--   3) :name 形式为应用层预编译参数占位符，勿直接作为 SQL 执行。
-- ============================================================================

DROP DATABASE IF EXISTS ticket_sales;
CREATE DATABASE ticket_sales
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
USE ticket_sales;

-- ============================================================================
-- 一、基础与维度表
-- ============================================================================

-- 1. 城市（约 100 个）
CREATE TABLE city (
  city_id     SMALLINT     NOT NULL AUTO_INCREMENT COMMENT '城市ID',
  city_name   VARCHAR(50)  NOT NULL COMMENT '城市名称',
  PRIMARY KEY (city_id),
  UNIQUE KEY uk_city_name (city_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='城市表';

-- 2. 演出类型（演唱会/话剧歌剧/体育/儿童亲子/展览……）
CREATE TABLE category (
  category_id   TINYINT     NOT NULL AUTO_INCREMENT COMMENT '类型ID',
  category_name VARCHAR(20) NOT NULL COMMENT '类型名称',
  PRIMARY KEY (category_id),
  UNIQUE KEY uk_category_name (category_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='演出类型字典表';

-- 3. 管理员
CREATE TABLE admin (
  admin_id      INT          NOT NULL AUTO_INCREMENT COMMENT '管理员ID',
  username      VARCHAR(50)  NOT NULL COMMENT '用户名',
  password_hash CHAR(60)     NOT NULL COMMENT '口令哈希(bcrypt)',
  real_name     VARCHAR(50)  DEFAULT NULL COMMENT '姓名',
  role          TINYINT      NOT NULL DEFAULT 1 COMMENT '1普通管理员 9超级管理员',
  create_time   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (admin_id),
  UNIQUE KEY uk_admin_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='管理员表';

-- 4. 用户（约 10 万人）
CREATE TABLE app_user (
  user_id       BIGINT       NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  username      VARCHAR(50)  NOT NULL COMMENT '用户名',
  password_hash CHAR(60)     NOT NULL COMMENT '口令哈希(bcrypt)',
  phone         VARCHAR(20)  NOT NULL COMMENT '手机号',
  email         VARCHAR(100) DEFAULT NULL COMMENT '邮箱',
  status        TINYINT      NOT NULL DEFAULT 1 COMMENT '1正常 0冻结',
  create_time   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
  PRIMARY KEY (user_id),
  UNIQUE KEY uk_user_username (username),
  UNIQUE KEY uk_user_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- 5. 场馆
CREATE TABLE venue (
  venue_id   INT          NOT NULL AUTO_INCREMENT COMMENT '场馆ID',
  city_id    SMALLINT     NOT NULL COMMENT '所在城市',
  venue_name VARCHAR(100) NOT NULL COMMENT '场馆名称',
  address    VARCHAR(200) NOT NULL COMMENT '详细地址',
  capacity   INT          NOT NULL DEFAULT 0 COMMENT '座位数',
  PRIMARY KEY (venue_id),
  UNIQUE KEY uk_venue_city_name (city_id, venue_name),
  KEY idx_venue_city (city_id),
  CONSTRAINT fk_venue_city FOREIGN KEY (city_id) REFERENCES city (city_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='场馆表';

-- ============================================================================
-- 二、演出域
-- ============================================================================

-- 6. 演出（项目）
CREATE TABLE show_item (
  show_id     INT          NOT NULL AUTO_INCREMENT COMMENT '演出ID',
  show_name   VARCHAR(100) NOT NULL COMMENT '演出名称',
  category_id TINYINT      NOT NULL COMMENT '演出类型',
  city_id     SMALLINT     NOT NULL COMMENT '所在城市',
  poster_url  VARCHAR(255) DEFAULT NULL COMMENT '海报图片URL',
  description TEXT         COMMENT '演出介绍文字',
  admin_id    INT          NOT NULL COMMENT '创建管理员',
  create_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (show_id),
  KEY idx_show_city_cat (city_id, category_id),   -- 列表：城市+类型筛选（最高频）
  KEY idx_show_category (category_id),
  KEY idx_show_name (show_name),
  CONSTRAINT fk_show_category FOREIGN KEY (category_id) REFERENCES category (category_id),
  CONSTRAINT fk_show_city     FOREIGN KEY (city_id)     REFERENCES city (city_id),
  CONSTRAINT fk_show_admin    FOREIGN KEY (admin_id)    REFERENCES admin (admin_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='演出表';

-- 7. 演出图片（弱实体，随演出级联删除）
CREATE TABLE show_image (
  image_id   BIGINT       NOT NULL AUTO_INCREMENT COMMENT '图片ID',
  show_id    INT          NOT NULL COMMENT '所属演出',
  image_url  VARCHAR(255) NOT NULL COMMENT '图片URL',
  sort_no    TINYINT      NOT NULL DEFAULT 0 COMMENT '展示顺序',
  PRIMARY KEY (image_id),
  KEY idx_image_show (show_id, sort_no),
  CONSTRAINT fk_image_show FOREIGN KEY (show_id) REFERENCES show_item (show_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='演出介绍图片表';

-- 8. 演出场次（弱实体：同一演出若干日期）
CREATE TABLE show_session (
  session_id  INT      NOT NULL AUTO_INCREMENT COMMENT '场次ID',
  show_id     INT      NOT NULL COMMENT '所属演出',
  venue_id    INT      NOT NULL COMMENT '演出场馆',
  show_time   DATETIME NOT NULL COMMENT '开演时间',
  sale_start  DATETIME NOT NULL COMMENT '开售时间(决定预售/售票中)',
  sale_status TINYINT  NOT NULL DEFAULT 1 COMMENT '1预售中 2售票中 3售罄',
  PRIMARY KEY (session_id),
  UNIQUE KEY uk_session_show_time (show_id, show_time),
  KEY idx_session_show_time (show_id, show_time),
  KEY idx_session_venue (venue_id),
  KEY idx_session_time (show_time),
  CONSTRAINT fk_session_show  FOREIGN KEY (show_id)  REFERENCES show_item (show_id) ON DELETE CASCADE,
  CONSTRAINT fk_session_venue FOREIGN KEY (venue_id) REFERENCES venue (venue_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='演出场次表';

-- 9. 票档（弱实体：每场若干档）
CREATE TABLE ticket_tier (
  tier_id     BIGINT       NOT NULL AUTO_INCREMENT COMMENT '票档ID',
  session_id  INT          NOT NULL COMMENT '所属场次',
  tier_name   VARCHAR(50)  NOT NULL COMMENT '票档名称(VIP/看台A...)',
  price       DECIMAL(8,2) NOT NULL COMMENT '单价',
  total_seats INT          NOT NULL COMMENT '总票数',
  sold_seats  INT          NOT NULL DEFAULT 0 COMMENT '已售票数',
  PRIMARY KEY (tier_id),
  UNIQUE KEY uk_tier_session_name (session_id, tier_name),
  KEY idx_tier_session (session_id),
  CONSTRAINT fk_tier_session FOREIGN KEY (session_id) REFERENCES show_session (session_id) ON DELETE CASCADE,
  CONSTRAINT chk_tier_price  CHECK (price > 0),
  CONSTRAINT chk_tier_seats  CHECK (total_seats > 0),
  CONSTRAINT chk_tier_sold   CHECK (sold_seats >= 0 AND sold_seats <= total_seats)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='票档表';

-- ============================================================================
-- 三、用户资料域
-- ============================================================================

-- 10. 收货信息
CREATE TABLE shipping_address (
  address_id     BIGINT       NOT NULL AUTO_INCREMENT COMMENT '收货信息ID',
  user_id        BIGINT       NOT NULL COMMENT '所属用户',
  receiver_name  VARCHAR(50)  NOT NULL COMMENT '收货人',
  phone          VARCHAR(20)  NOT NULL COMMENT '手机号',
  address_detail VARCHAR(200) NOT NULL COMMENT '收货地址',
  is_default     TINYINT      NOT NULL DEFAULT 0 COMMENT '是否默认 1是 0否',
  create_time    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (address_id),
  KEY idx_addr_user (user_id),
  CONSTRAINT fk_addr_user FOREIGN KEY (user_id) REFERENCES app_user (user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='收货信息表';

-- 11. 常用购票人
CREATE TABLE attendee (
  attendee_id   BIGINT      NOT NULL AUTO_INCREMENT COMMENT '购票人ID',
  user_id       BIGINT      NOT NULL COMMENT '所属用户',
  attendee_name VARCHAR(50) NOT NULL COMMENT '姓名',
  id_type       TINYINT     NOT NULL COMMENT '证件类型 1身份证 2护照 3港澳通行证 4台胞证 5军官证',
  id_no         VARCHAR(30) NOT NULL COMMENT '证件号',
  create_time   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (attendee_id),
  UNIQUE KEY uk_attendee_cert (user_id, id_type, id_no),
  KEY idx_attendee_user (user_id),
  CONSTRAINT fk_attendee_user FOREIGN KEY (user_id) REFERENCES app_user (user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='常用购票人表';

-- ============================================================================
-- 四、交易域（数据量最大的域）
-- ============================================================================

-- 12. 订单（一次下单 = 一个场次 + 一个票档 + N 张票）
CREATE TABLE ticket_order (
  order_id     BIGINT        NOT NULL AUTO_INCREMENT COMMENT '订单ID',
  order_no     VARCHAR(32)   NOT NULL COMMENT '业务订单号',
  user_id      BIGINT        NOT NULL COMMENT '下单用户',
  session_id   INT           NOT NULL COMMENT '演出场次',
  tier_id      BIGINT        NOT NULL COMMENT '票档',
  address_id   BIGINT        NOT NULL COMMENT '收货信息',
  ticket_count INT           NOT NULL COMMENT '票数',
  total_amount DECIMAL(10,2) NOT NULL COMMENT '订单金额(快照)',
  order_status TINYINT       NOT NULL DEFAULT 1 COMMENT '1待支付 2已支付 3已取消 4已退款',
  create_time  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '下单时间',
  pay_time     DATETIME      DEFAULT NULL COMMENT '支付时间',
  PRIMARY KEY (order_id),
  UNIQUE KEY uk_order_no (order_no),
  KEY idx_order_user_time (user_id, create_time),     -- 我的订单
  KEY idx_order_status_pay (order_status, pay_time),  -- 时间段统计
  KEY idx_order_session (session_id),
  CONSTRAINT fk_order_user    FOREIGN KEY (user_id)    REFERENCES app_user (user_id),
  CONSTRAINT fk_order_session FOREIGN KEY (session_id) REFERENCES show_session (session_id),
  CONSTRAINT fk_order_tier    FOREIGN KEY (tier_id)    REFERENCES ticket_tier (tier_id),
  CONSTRAINT fk_order_addr    FOREIGN KEY (address_id) REFERENCES shipping_address (address_id),
  CONSTRAINT chk_order_count  CHECK (ticket_count BETWEEN 1 AND 6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表';

-- 13. 订单明细（每张票一行，绑定一位购票人）
CREATE TABLE order_item (
  item_id      BIGINT       NOT NULL AUTO_INCREMENT COMMENT '明细ID',
  order_id     BIGINT       NOT NULL COMMENT '所属订单',
  tier_id      BIGINT       NOT NULL COMMENT '票档',
  attendee_id  BIGINT       NOT NULL COMMENT '持票购票人',
  session_id   INT          NOT NULL COMMENT '场次(冗余, 服务于限购唯一约束)',
  unit_price   DECIMAL(8,2) NOT NULL COMMENT '成交单价(快照)',
  PRIMARY KEY (item_id),
  UNIQUE KEY uk_item_attendee_session (attendee_id, session_id),  -- 限购：每人每场1张
  KEY idx_item_order (order_id),
  KEY idx_item_tier (tier_id),
  CONSTRAINT fk_item_order    FOREIGN KEY (order_id)    REFERENCES ticket_order (order_id) ON DELETE CASCADE,
  CONSTRAINT fk_item_tier     FOREIGN KEY (tier_id)     REFERENCES ticket_tier (tier_id),
  CONSTRAINT fk_item_attendee FOREIGN KEY (attendee_id) REFERENCES attendee (attendee_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单明细表';

-- 14. 购票请求日志（成功/失败全部记录）
CREATE TABLE purchase_request (
  request_id   BIGINT       NOT NULL AUTO_INCREMENT COMMENT '请求ID',
  user_id      BIGINT       NOT NULL COMMENT '请求用户',
  session_id   INT          NOT NULL COMMENT '场次',
  tier_id      BIGINT       NOT NULL COMMENT '票档',
  ticket_count INT          NOT NULL COMMENT '请求票数',
  result       TINYINT      NOT NULL COMMENT '1成功 0失败',
  fail_reason  VARCHAR(100) DEFAULT NULL COMMENT '失败原因',
  request_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '请求时间',
  PRIMARY KEY (request_id),
  KEY idx_req_user_time (user_id, request_time),
  KEY idx_req_time (request_time),
  KEY idx_req_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='购票请求日志表';

-- 15. 销售日汇总（统计加速表，支付成功后由触发器/事务维护）
CREATE TABLE sales_daily (
  stat_date    DATE          NOT NULL COMMENT '统计日期',
  order_count  INT           NOT NULL DEFAULT 0 COMMENT '成交订单数',
  ticket_count INT           NOT NULL DEFAULT 0 COMMENT '售票张数',
  total_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '销售金额',
  PRIMARY KEY (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='销售日汇总表';

-- ============================================================================
-- 五、触发器：支付成功后累加销售日汇总
--   （订单状态 1待支付 -> 2已支付 时累加；退款 4 可对称扣减，此处略）
-- ============================================================================
DELIMITER //
CREATE TRIGGER trg_order_paid
AFTER UPDATE ON ticket_order
FOR EACH ROW
BEGIN
  IF NEW.order_status = 2 AND OLD.order_status <> 2 AND NEW.pay_time IS NOT NULL THEN
    INSERT INTO sales_daily (stat_date, order_count, ticket_count, total_amount)
    VALUES (DATE(NEW.pay_time), 1, NEW.ticket_count, NEW.total_amount)
    ON DUPLICATE KEY UPDATE
      order_count  = order_count  + 1,
      ticket_count = ticket_count + NEW.ticket_count,
      total_amount = total_amount + NEW.total_amount;
  END IF;
END//
DELIMITER ;

-- ============================================================================
-- 六、初始化字典数据
-- ============================================================================
INSERT INTO category (category_name) VALUES
  ('演唱会'), ('话剧歌剧'), ('体育'), ('儿童亲子'), ('展览'), ('音乐会'), ('舞蹈芭蕾');

INSERT INTO city (city_name) VALUES
  ('北京'), ('上海'), ('广州'), ('深圳'), ('杭州'), ('成都'), ('武汉'), ('西安');

-- ============================================================================
-- 七、业务视图（与 views.sql 内容一致；已导入过旧版 ddl 的库可单独运行 views.sql）
-- ============================================================================

-- 视图 1：演出列表（名称/城市/类型/地点/最近日期/票价区间/售票状态聚合）
CREATE OR REPLACE VIEW v_show_list AS
SELECT
  s.show_id, s.show_name, s.poster_url,
  c.city_id, c.city_name,
  cat.category_id, cat.category_name,
  ev.venue_name,
  MIN(se.show_time) AS nearest_show_time,
  MIN(t.price)      AS min_price,
  MAX(t.price)      AS max_price,
  CASE
    WHEN MAX(se.sale_status = 2) > 0 THEN 2
    WHEN MAX(se.sale_status = 1) > 0 THEN 1
    ELSE 3
  END AS show_status
FROM show_item s
JOIN city c        ON c.city_id = s.city_id
JOIN category cat  ON cat.category_id = s.category_id
LEFT JOIN show_session se ON se.show_id = s.show_id
LEFT JOIN ticket_tier  t  ON t.session_id = se.session_id
LEFT JOIN (
    SELECT se2.show_id, v2.venue_name
    FROM show_session se2
    JOIN venue v2 ON v2.venue_id = se2.venue_id
    WHERE (se2.show_id, se2.show_time) IN (
        SELECT show_id, MIN(show_time) FROM show_session GROUP BY show_id
    )
) ev ON ev.show_id = s.show_id
GROUP BY s.show_id, s.show_name, s.poster_url,
         c.city_id, c.city_name, cat.category_id, cat.category_name, ev.venue_name;

-- 视图 2：票档余票（余票数 + 售罄标记，详情页“该票档售罄”数据源）
CREATE OR REPLACE VIEW v_tier_stock AS
SELECT t.tier_id, t.session_id, t.tier_name, t.price,
       t.total_seats, t.sold_seats,
       t.total_seats - t.sold_seats AS remain_seats,
       CASE WHEN t.total_seats - t.sold_seats = 0 THEN 1 ELSE 0 END AS sold_out
FROM ticket_tier t;

-- 视图 3：订单详情（“我的订单”列表数据源）
CREATE OR REPLACE VIEW v_order_detail AS
SELECT o.order_id, o.order_no, o.ticket_count, o.total_amount,
       o.order_status, o.create_time, o.pay_time,
       s.show_name, v.venue_name, c.city_name, se.show_time,
       addr.receiver_name, addr.phone, addr.address_detail
FROM ticket_order o
JOIN show_session se       ON se.session_id = o.session_id
JOIN show_item s           ON s.show_id = se.show_id
JOIN venue v               ON v.venue_id = se.venue_id
JOIN city c                ON c.city_id = v.city_id
JOIN shipping_address addr ON addr.address_id = o.address_id;

-- ============================================================================
-- 附录：大数据量分区改造（替代上文 ticket_order / purchase_request 定义）
-- ----------------------------------------------------------------------------
-- 适用场景：订单年增 ~140 万、请求日志年增 ~500 万，5 年以上增长。
-- 注意：MySQL InnoDB 分区表【不支持外键】（不能引用也不能被引用），
--       因此分区版删除这两张表的外键约束，参照完整性改由应用层事务 +
--       每日对账作业保证；order_item 建议保留非分区（其限购唯一键
--       (attendee_id, session_id) 不能含分区键），但需去掉到 ticket_order
--       的外键（分区表不能被外键引用），到 ticket_tier / attendee 的外键保留。
-- 每年初提前创建下一年分区（可用调度事件自动 ADD PARTITION）。
-- ----------------------------------------------------------------------------
/*
CREATE TABLE ticket_order_p (
  order_id     BIGINT        NOT NULL AUTO_INCREMENT,
  order_no     VARCHAR(32)   NOT NULL,
  user_id      BIGINT        NOT NULL,
  session_id   INT           NOT NULL,
  tier_id      BIGINT        NOT NULL,
  address_id   BIGINT        NOT NULL,
  ticket_count INT           NOT NULL,
  total_amount DECIMAL(10,2) NOT NULL,
  order_status TINYINT       NOT NULL DEFAULT 1,
  create_time  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  pay_time     DATETIME      DEFAULT NULL,
  PRIMARY KEY (order_id, create_time),
  UNIQUE KEY uk_order_no (order_no, create_time),
  KEY idx_order_user_time (user_id, create_time),
  KEY idx_order_status_pay (order_status, pay_time),
  KEY idx_order_session (session_id),
  CONSTRAINT chk_p_order_count CHECK (ticket_count BETWEEN 1 AND 6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
PARTITION BY RANGE (YEAR(create_time)) (
  PARTITION p2022 VALUES LESS THAN (2023),
  PARTITION p2023 VALUES LESS THAN (2024),
  PARTITION p2024 VALUES LESS THAN (2025),
  PARTITION p2025 VALUES LESS THAN (2026),
  PARTITION p2026 VALUES LESS THAN (2027),
  PARTITION pmax  VALUES LESS THAN MAXVALUE
);

CREATE TABLE purchase_request_p (
  request_id   BIGINT       NOT NULL AUTO_INCREMENT,
  user_id      BIGINT       NOT NULL,
  session_id   INT          NOT NULL,
  tier_id      BIGINT       NOT NULL,
  ticket_count INT          NOT NULL,
  result       TINYINT      NOT NULL,
  fail_reason  VARCHAR(100) DEFAULT NULL,
  request_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (request_id, request_time),
  KEY idx_req_user_time (user_id, request_time),
  KEY idx_req_time (request_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
PARTITION BY RANGE (YEAR(request_time)) (
  PARTITION p2022 VALUES LESS THAN (2023),
  PARTITION p2023 VALUES LESS THAN (2024),
  PARTITION p2024 VALUES LESS THAN (2025),
  PARTITION p2025 VALUES LESS THAN (2026),
  PARTITION p2026 VALUES LESS THAN (2027),
  PARTITION pmax  VALUES LESS THAN MAXVALUE
);
-- 历史日志归档：ALTER TABLE purchase_request_p DROP PARTITION p2022;
*/
