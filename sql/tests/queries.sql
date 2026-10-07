-- ============================================================================
-- 演出门票销售系统 典型业务查询与统计 SQL (MySQL 8.0)
-- 对应文档：《演出门票销售系统_数据库设计.md》
-- :name 形式为应用层预编译参数占位符（防 SQL 注入），需绑定参数执行；
-- 口令校验在应用层用 bcrypt 完成，数据库只按用户名取哈希串。
-- ============================================================================
USE ticket_sales;

-- ============================================================================
-- 一、游客/用户：登录
-- ============================================================================
-- 1.1 用户登录（取哈希，由应用层 bcrypt.verify(input, password_hash) 判定）
SELECT user_id, username, password_hash, status
FROM app_user
WHERE username = :username;
-- 命中且 status=1 且 bcrypt 校验通过 -> 跳转已登录页面；否则提示登录失败。

-- 1.2 管理员登录
SELECT admin_id, username, password_hash, role
FROM admin
WHERE username = :username;

-- ============================================================================
-- 二、游客：演出列表（按城市、类型筛选；价格区间、售票状态聚合）
-- ============================================================================
-- 2.1 列表页：可选城市(:city_id 可空=全部)、可选类型(:cat_id 可空=全部)
SELECT
  s.show_id,
  s.show_name,
  c.city_name,
  cat.category_name,
  v.venue_name,
  (SELECT MIN(se2.show_time)
     FROM show_session se2
     WHERE se2.show_id = s.show_id AND se2.show_time >= NOW())   -- 最近一场
    AS nearest_date,
  (SELECT MIN(t.price) FROM ticket_tier t
     JOIN show_session se3 ON se3.session_id = t.session_id
     WHERE se3.show_id = s.show_id) AS min_price,               -- 最低价
  (SELECT MAX(t.price) FROM ticket_tier t
     JOIN show_session se3 ON se3.session_id = t.session_id
     WHERE se3.show_id = s.show_id) AS max_price,               -- 最高价
  /* 售票状态聚合：实时依据开售时间和余票计算，避免依赖事件调度器 */
  (SELECT CASE
            WHEN SUM(CASE WHEN se4.show_time > NOW() AND se4.sale_start <= NOW()
                                AND EXISTS (SELECT 1 FROM ticket_tier t4
                                            WHERE t4.session_id=se4.session_id
                                              AND t4.total_seats-t4.sold_seats > 0)
                           THEN 1 ELSE 0 END) > 0 THEN 2
            WHEN SUM(CASE WHEN se4.sale_start > NOW() AND se4.show_time > NOW() THEN 1 ELSE 0 END) > 0 THEN 1
            WHEN SUM(CASE WHEN se4.show_time > NOW() THEN 1 ELSE 0 END) > 0 THEN 3
            WHEN SUM(CASE WHEN se4.show_time <= NOW() THEN 1 ELSE 0 END) > 0 THEN 4
            ELSE 3
          END
     FROM show_session se4 WHERE se4.show_id = s.show_id) AS show_status
FROM show_item s
JOIN city c       ON c.city_id = s.city_id
JOIN category cat ON cat.category_id = s.category_id
LEFT JOIN venue v ON v.venue_id = (SELECT se.venue_id FROM show_session se
                                   WHERE se.show_id = s.show_id
                                   ORDER BY se.show_time LIMIT 1)  -- 无场次演出不丢失
WHERE (:city_id IS NULL OR s.city_id = :city_id)
  AND (:cat_id  IS NULL OR s.category_id = :cat_id)
ORDER BY s.create_time DESC
LIMIT :offset, :size;                         -- 分页

-- 2.2 为加速列表，可建视图（与 2.1 等价，供前端直接 SELECT ... WHERE）
CREATE OR REPLACE VIEW v_show_list AS
SELECT
  s.show_id, s.show_name, s.poster_url,
  s.series_id, ser.series_name,
  c.city_id, c.city_name,
  cat.category_id, cat.category_name,
  ev.venue_name,                                   -- 最近场次所在场馆(地点)
  MIN(se.show_time) AS nearest_show_time,
  GROUP_CONCAT(DISTINCT DATE_FORMAT(se.show_time, '%m.%d')
               ORDER BY se.show_time SEPARATOR ' / ') AS show_dates,
  MIN(t.price)      AS min_price,
  MAX(t.price)      AS max_price,
  CASE
    WHEN MAX(se.sale_status = 2) > 0 THEN 2   -- 有场次售票中
    WHEN MAX(se.sale_status = 1) > 0 THEN 1   -- 否则有场次预售中
    WHEN MAX(se.sale_status = 3) > 0 THEN 3   -- 否则有未来售罄场次
    WHEN MAX(se.sale_status = 4) > 0 THEN 4   -- 全部已结束
    ELSE 3
  END AS show_status
FROM show_item s
JOIN city c        ON c.city_id = s.city_id
JOIN category cat  ON cat.category_id = s.category_id
LEFT JOIN show_series ser ON ser.series_id = s.series_id
LEFT JOIN (
    SELECT se0.session_id, se0.show_id, se0.show_time,
           CASE
             WHEN se0.show_time <= NOW() THEN 4
             WHEN se0.sale_start > NOW() THEN 1
             WHEN COALESCE(SUM(t0.total_seats-t0.sold_seats),0) > 0 THEN 2
             ELSE 3
           END AS sale_status
    FROM show_session se0
    LEFT JOIN ticket_tier t0 ON t0.session_id=se0.session_id
    GROUP BY se0.session_id, se0.show_id, se0.show_time, se0.sale_start
) se ON se.show_id = s.show_id
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
         s.series_id, ser.series_name,
         c.city_id, c.city_name, cat.category_id, cat.category_name, ev.venue_name;

-- 列表走视图（城市/类型过滤 + 分页）
SELECT * FROM v_show_list
WHERE (:city_id IS NULL OR city_id = :city_id)
  AND (:cat_id  IS NULL OR category_id = :cat_id)
ORDER BY nearest_show_time
LIMIT :offset, :size;

-- ============================================================================
-- 三、游客：演出详情
-- ============================================================================
-- 3.1 演出基本信息（名称、地点、海报、介绍文字、价格区间、整体状态）
SELECT s.show_id, s.show_name, s.poster_url, s.description,
       c.city_name, cat.category_name,
       (SELECT MIN(price) FROM ticket_tier t
          JOIN show_session se ON se.session_id = t.session_id
          WHERE se.show_id = s.show_id) AS min_price,
       (SELECT MAX(price) FROM ticket_tier t
          JOIN show_session se ON se.session_id = t.session_id
          WHERE se.show_id = s.show_id) AS max_price
FROM show_item s
JOIN city c ON c.city_id = s.city_id
JOIN category cat ON cat.category_id = s.category_id
WHERE s.show_id = :show_id;

-- 3.2 演出介绍图片（多张，按排序号）
SELECT image_url, sort_no
FROM show_image
WHERE show_id = :show_id
ORDER BY sort_no, image_id;

-- 3.3 演出日期列表（若干场次：时间、场馆、状态）
SELECT se.session_id, se.show_time, v.venue_name, v.address,
       CASE
         WHEN se.show_time <= NOW() THEN 4
         WHEN se.sale_start > NOW() THEN 1
         WHEN EXISTS (SELECT 1 FROM ticket_tier tx
                      WHERE tx.session_id=se.session_id
                        AND tx.total_seats-tx.sold_seats > 0) THEN 2
         ELSE 3
       END AS sale_status,
       (SELECT MIN(price) FROM ticket_tier t WHERE t.session_id = se.session_id) AS min_p,
       (SELECT MAX(price) FROM ticket_tier t WHERE t.session_id = se.session_id) AS max_p
FROM show_session se
JOIN venue v ON v.venue_id = se.venue_id
WHERE se.show_id = :show_id
ORDER BY se.show_time;

-- 3.4 票档列表（无余票 -> 前端显示“该票档售罄”）
CREATE OR REPLACE VIEW v_tier_stock AS
SELECT t.tier_id, t.session_id, t.tier_name, t.price,
       t.total_seats, t.sold_seats,
       t.total_seats - t.sold_seats AS remain_seats,
       CASE WHEN t.total_seats - t.sold_seats = 0 THEN 1 ELSE 0 END AS sold_out
FROM ticket_tier t;

SELECT tier_id, tier_name, price, total_seats, sold_seats, remain_seats, sold_out
FROM v_tier_stock
WHERE session_id = :session_id
ORDER BY price;

-- ============================================================================
-- 四、用户：个人资料维护
-- ============================================================================
-- 4.1 收货信息：增 / 查 / 改 / 删
INSERT INTO shipping_address (user_id, receiver_name, phone, address_detail, is_default)
VALUES (:user_id, :receiver_name, :phone, :address_detail, :is_default);

SELECT address_id, receiver_name, phone, address_detail, is_default
FROM shipping_address WHERE user_id = :user_id ORDER BY is_default DESC, address_id;

UPDATE shipping_address
SET receiver_name = :receiver_name, phone = :phone,
    address_detail = :address_detail, is_default = :is_default
WHERE address_id = :address_id AND user_id = :user_id;

DELETE FROM shipping_address WHERE address_id = :address_id AND user_id = :user_id;

-- 4.2 常用购票人：增 / 查 / 删
INSERT INTO attendee (user_id, attendee_name, id_type, id_no)
VALUES (:user_id, :attendee_name, :id_type, :id_no);

SELECT attendee_id, attendee_name,
       ELT(id_type, '身份证','护照','港澳通行证','台胞证','军官证') AS id_type_name,
       id_no
FROM attendee WHERE user_id = :user_id ORDER BY attendee_id;

DELETE FROM attendee WHERE attendee_id = :attendee_id AND user_id = :user_id;

-- ============================================================================
-- 五、用户：购票（核心事务：扣余票 + 限购 + 生成订单 + 请求留痕）
--   参数：:user_id :session_id :tier_id :n(票数) :address_id
--         :attendee_ids = [..](n 位购票人，每人 1 张)
--   应用层伪代码：
--     BEGIN;
--       ① 写请求日志(结果待定) -> ② 原子扣票 -> ③ 写订单 ->
--       ④ 逐张写明细(限购唯一键兜底) -> ⑤ 更新日志为成功;
--     COMMIT;  任一步失败 ROLLBACK 并把请求标记失败(余票不足/超出限购)。
-- ============================================================================

-- ① 记录购票请求（先落库，结果最后回填；若进程崩溃也有“未知/处理中”记录可巡检）
INSERT INTO purchase_request (user_id, session_id, tier_id, ticket_count, result, fail_reason)
VALUES (:user_id, :session_id, :tier_id, :n, 0, '处理中');
SET @request_id = LAST_INSERT_ID();

-- ② 原子扣减余票（InnoDB 行锁串行化；影响行数=0 即余票不足，判定失败回滚）
UPDATE ticket_tier
SET sold_seats = sold_seats + :n
WHERE tier_id = :tier_id
  AND total_seats - sold_seats >= :n;

-- ③ 生成订单（order_no 由应用层生成，如 yyyyMMddHHmmss + 6 位随机串；
--    total_amount = 票档单价 × :n，应用层算好传入；状态 1 待支付）
INSERT INTO ticket_order
  (order_no, user_id, session_id, tier_id, address_id, ticket_count, total_amount, order_status)
VALUES
  (:order_no, :user_id, :session_id, :tier_id, :address_id, :n, :total_amount, 1);
SET @order_id = LAST_INSERT_ID();

-- ④ 逐张写入明细，每张绑定一位购票人（循环执行 n 次）；
--    若 (attendee_id, session_id) 已存在 -> 1062 唯一冲突 = 超出限购，回滚
INSERT INTO order_item (order_id, tier_id, attendee_id, session_id, unit_price)
VALUES (@order_id, :tier_id, :attendee_id, :session_id, :unit_price);

-- ⑤ 支付成功（演示中可直接置为已支付；生产环境由支付回调更新，
--    更新后触发器 trg_order_paid 自动累加 sales_daily）
UPDATE ticket_order
SET order_status = 2, pay_time = NOW()
WHERE order_id = @order_id;

-- ⑥ 请求日志回填成功（失败路径：UPDATE ... SET result=0, fail_reason='余票不足'/'超出限购'）
UPDATE purchase_request SET result = 1, fail_reason = NULL
WHERE request_id = @request_id;

-- 失败请求统计口径示例（管理员可查某时段失败原因分布）
SELECT fail_reason, COUNT(*) AS cnt
FROM purchase_request
WHERE result = 0 AND request_time BETWEEN :start AND :end
GROUP BY fail_reason ORDER BY cnt DESC;

-- ============================================================================
-- 六、用户：我的订单
-- ============================================================================
CREATE OR REPLACE VIEW v_order_detail AS
SELECT o.order_id, o.order_no, o.ticket_count, o.total_amount,
       o.order_status, o.create_time, o.pay_time,
       s.show_name, v.venue_name, c.city_name, se.show_time,
       addr.receiver_name, addr.phone, addr.address_detail
FROM ticket_order o
JOIN app_user u         ON u.user_id = o.user_id
JOIN show_session se    ON se.session_id = o.session_id
JOIN show_item s        ON s.show_id = se.show_id
JOIN venue v            ON v.venue_id = se.venue_id
JOIN city c             ON c.city_id = v.city_id  -- 场馆所在城市
JOIN shipping_address addr ON addr.address_id = o.address_id;

-- 订单列表：订单号、演出名称、地点、演出日期、票数、金额、状态、收货信息
SELECT order_no, show_name,
       CONCAT(city_name, venue_name) AS place,
       show_time, ticket_count, total_amount,
       ELT(order_status, '待支付','已支付','已取消','已退款') AS status_text,
       CONCAT(receiver_name, ' ', phone, ' ', address_detail) AS shipping
FROM v_order_detail
WHERE order_id IN (SELECT order_id FROM ticket_order
                   WHERE user_id = :user_id)
ORDER BY create_time DESC
LIMIT :offset, :size;

-- 订单详情：每张票的持票人
SELECT oi.item_id, oi.unit_price, a.attendee_name,
       ELT(a.id_type, '身份证','护照','港澳通行证','台胞证','军官证') AS id_type_name,
       a.id_no
FROM order_item oi
JOIN attendee a ON a.attendee_id = oi.attendee_id
WHERE oi.order_id = :order_id;

-- ============================================================================
-- 七、管理员：销售统计（按时间段，图表取数）
-- ============================================================================
-- 7.1 按天统计【走汇总表，毫秒级】——折线图/柱状图
SELECT stat_date AS d,
       order_count,
       ticket_count AS tickets,
       total_amount AS amount
FROM sales_daily
WHERE stat_date BETWEEN :start AND :end
ORDER BY stat_date;

-- 7.2 按天统计【实时明细聚合，自定义任意时间段】——走 (order_status, pay_time) 索引
SELECT DATE(pay_time) AS d,
       COUNT(*)              AS order_count,
       SUM(ticket_count)     AS tickets,
       SUM(total_amount)     AS amount
FROM ticket_order
WHERE order_status = 2                       -- 已支付
  AND pay_time BETWEEN :start AND :end
GROUP BY DATE(pay_time)
ORDER BY d;

-- 7.3 按演出类型统计时间段销量（饼图）
SELECT cat.category_name,
       SUM(o.ticket_count)  AS tickets,
       SUM(o.total_amount)  AS amount
FROM ticket_order o
JOIN show_session se ON se.session_id = o.session_id
JOIN show_item s     ON s.show_id = se.show_id
JOIN category cat    ON cat.category_id = s.category_id
WHERE o.order_status = 2
  AND o.pay_time BETWEEN :start AND :end
GROUP BY cat.category_id, cat.category_name
ORDER BY amount DESC;

-- 7.4 按城市统计时间段销量（柱状图/地图）
SELECT c.city_name,
       SUM(o.ticket_count) AS tickets,
       SUM(o.total_amount) AS amount
FROM ticket_order o
JOIN show_session se ON se.session_id = o.session_id
JOIN venue v         ON v.venue_id = se.venue_id
JOIN city c          ON c.city_id = v.city_id
WHERE o.order_status = 2
  AND o.pay_time BETWEEN :start AND :end
GROUP BY c.city_id, c.city_name
ORDER BY amount DESC;

-- 7.5 热销演出 TOP 10（时间段内）
SELECT s.show_name, c.city_name,
       SUM(o.ticket_count) AS tickets,
       SUM(o.total_amount) AS amount
FROM ticket_order o
JOIN show_session se ON se.session_id = o.session_id
JOIN show_item s     ON s.show_id = se.show_id
JOIN city c          ON c.city_id = s.city_id
WHERE o.order_status = 2
  AND o.pay_time BETWEEN :start AND :end
GROUP BY s.show_id, s.show_name, c.city_name
ORDER BY tickets DESC
LIMIT 10;

-- 7.6 单场上座率（售票情况）
SELECT s.show_name, se.show_time, v.venue_name,
       t.tier_name, t.total_seats, t.sold_seats,
       ROUND(t.sold_seats / t.total_seats * 100, 1) AS sell_through_pct
FROM ticket_tier t
JOIN show_session se ON se.session_id = t.session_id
JOIN show_item s     ON s.show_id = se.show_id
JOIN venue v         ON v.venue_id = se.venue_id
WHERE se.session_id = :session_id
ORDER BY t.price;
