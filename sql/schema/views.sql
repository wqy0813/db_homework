-- ============================================================================
-- 演出门票销售系统 业务视图脚本 (MySQL 8.0)
-- 作用：创建列表/详情/订单所用的 3 个视图。
-- 用法：在已导入 ddl.sql + seed_data.sql 之后，本脚本【运行一次】即可
--       （右键 ticket_sales 库 → 运行 SQL 文件 → 选择本文件；
--         或新建查询粘贴本文件内容运行）。CREATE OR REPLACE 可重复执行。
-- ============================================================================
USE ticket_sales;

-- ----------------------------------------------------------------------------
-- 视图 1：演出列表视图（名称、城市、类型、地点、最近演出日期、
--         票价最低-最高、演出级售票状态）
--   状态聚合规则：使用 show_session.sale_status 物化状态；系列重平衡脚本
--                 保证每个系列最多一个城市站为在售。
--   地点取“最近一场演出”所在场馆。
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_show_list AS
SELECT
  s.show_id,
  s.show_name,
  s.poster_url,
  s.series_id,
  ser.series_name,
  c.city_id,
  c.city_name,
  cat.category_id,
  cat.category_name,
  ev.venue_name,
  MIN(se.show_time) AS nearest_show_time,
  GROUP_CONCAT(DISTINCT DATE_FORMAT(se.show_time, '%m.%d')
               ORDER BY se.show_time SEPARATOR ' / ') AS show_dates,
  MIN(t.price)      AS min_price,
  MAX(t.price)      AS max_price,
  CASE
    WHEN MAX(se.sale_status = 2) > 0 THEN 2   -- 有场次售票中
    WHEN MAX(se.sale_status = 1) > 0 THEN 1   -- 否则有场次预售中
    WHEN MAX(se.sale_status = 3) > 0 THEN 3   -- 否则有未来场次售罄
    WHEN MAX(se.sale_status = 4) > 0 THEN 4   -- 全部场次已结束
    ELSE 3
  END AS show_status
FROM show_item s
JOIN city c        ON c.city_id = s.city_id
JOIN category cat  ON cat.category_id = s.category_id
LEFT JOIN show_series ser ON ser.series_id = s.series_id
LEFT JOIN (
    SELECT se0.session_id, se0.show_id, se0.venue_id, se0.show_time,
           se0.sale_start, se0.sale_status
    FROM show_session se0
) se ON se.show_id = s.show_id
LEFT JOIN ticket_tier  t  ON t.session_id = se.session_id
LEFT JOIN (
    -- 每个演出“最近一场”所在的场馆（作为列表地点）
    SELECT se2.show_id, v2.venue_name
    FROM show_session se2
    JOIN venue v2 ON v2.venue_id = se2.venue_id
    WHERE (se2.show_id, se2.show_time) IN (
        SELECT show_id, MIN(show_time)
        FROM show_session
        GROUP BY show_id
    )
) ev ON ev.show_id = s.show_id
GROUP BY s.show_id, s.show_name, s.poster_url,
         s.series_id, ser.series_name,
         c.city_id, c.city_name,
         cat.category_id, cat.category_name,
         ev.venue_name;

-- ----------------------------------------------------------------------------
-- 视图 2：票档余票视图（余票数 + 售罄标记，详情页“该票档售罄”数据源）
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_tier_stock AS
SELECT t.tier_id,
       t.session_id,
       t.tier_name,
       t.price,
       t.total_seats,
       t.sold_seats,
       t.total_seats - t.sold_seats AS remain_seats,
       CASE WHEN t.total_seats - t.sold_seats = 0 THEN 1 ELSE 0 END AS sold_out
FROM ticket_tier t;

-- ----------------------------------------------------------------------------
-- 视图 3：订单详情视图（订单号、演出名称、地点、演出日期、票数、金额、
--         交易状态、收货信息——“我的订单”列表数据源）
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_order_detail AS
SELECT o.order_id,
       o.order_no,
       o.ticket_count,
       o.total_amount,
       o.order_status,
       o.create_time,
       o.pay_time,
       s.show_name,
       v.venue_name,
       c.city_name,
       se.show_time,
       addr.receiver_name,
       addr.phone,
       addr.address_detail
FROM ticket_order o
JOIN show_session se       ON se.session_id = o.session_id
JOIN show_item s           ON s.show_id = se.show_id
JOIN venue v               ON v.venue_id = se.venue_id
JOIN city c                ON c.city_id = v.city_id
JOIN shipping_address addr ON addr.address_id = o.address_id;

-- ----------------------------------------------------------------------------
-- 验证（应分别返回 8 / 49 / 9 左右的行数，无 1146 报错）
-- ----------------------------------------------------------------------------
-- SELECT COUNT(*) FROM v_show_list;     -- 预期 8
-- SELECT COUNT(*) FROM v_tier_stock;    -- 预期 49
-- SELECT COUNT(*) FROM v_order_detail;  -- 预期 9（订单数）
