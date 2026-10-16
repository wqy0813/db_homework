-- Upgrade an existing database without deleting orders or business data.
USE ticket_sales;

ALTER TABLE app_user MODIFY COLUMN password_hash VARCHAR(255) NOT NULL;
ALTER TABLE admin MODIFY COLUMN password_hash VARCHAR(255) NOT NULL;

-- Correct only the known seed order's attendee ownership. Preserve each
-- passenger's name/document and all order amounts, prices and payment times.
START TRANSACTION;
INSERT INTO attendee (user_id, attendee_name, id_type, id_no)
SELECT DISTINCT o.user_id, a.attendee_name, a.id_type, a.id_no
FROM ticket_order o
JOIN order_item oi ON oi.order_id=o.order_id
JOIN attendee a ON a.attendee_id=oi.attendee_id
WHERE o.order_no='NO20250103001' AND o.user_id=1
  AND o.session_id=1 AND oi.session_id=1 AND oi.unit_price=580.00
  AND a.user_id=4
  AND a.id_no IN ('330103198707073333','330103201601028888')
ON DUPLICATE KEY UPDATE attendee_id=attendee.attendee_id;

UPDATE order_item oi
JOIN ticket_order o ON o.order_id=oi.order_id
JOIN attendee old_a ON old_a.attendee_id=oi.attendee_id
JOIN attendee owned_a ON owned_a.user_id=o.user_id
  AND owned_a.id_type=old_a.id_type AND owned_a.id_no=old_a.id_no
  AND owned_a.attendee_name=old_a.attendee_name
SET oi.attendee_id=owned_a.attendee_id
WHERE o.order_no='NO20250103001' AND o.user_id=1
  AND o.session_id=1 AND oi.session_id=1 AND oi.unit_price=580.00
  AND old_a.user_id=4
  AND old_a.id_no IN ('330103198707073333','330103201601028888');
COMMIT;

CREATE OR REPLACE VIEW v_order_detail AS
SELECT o.order_id,
       o.order_no,
       o.user_id,
       o.ticket_count,
       o.total_amount,
       o.order_status,
       o.create_time,
       o.pay_time,
       s.show_name,
       v.venue_name,
       c.city_name,
       se.show_time,
       t.tier_name,
       COALESCE((SELECT oi.unit_price FROM order_item oi WHERE oi.order_id = o.order_id LIMIT 1), t.price) AS unit_price,
       addr.receiver_name,
       addr.phone,
       addr.address_detail
FROM ticket_order o
JOIN show_session se       ON se.session_id = o.session_id
JOIN show_item s           ON s.show_id = se.show_id
JOIN venue v               ON v.venue_id = se.venue_id
JOIN city c                ON c.city_id = v.city_id
JOIN ticket_tier t         ON t.tier_id = o.tier_id
JOIN shipping_address addr ON addr.address_id = o.address_id;

DELIMITER //
DROP TRIGGER IF EXISTS trg_order_paid_insert//
CREATE TRIGGER trg_order_paid_insert
AFTER INSERT ON ticket_order
FOR EACH ROW
BEGIN
  IF NEW.order_status = 2 AND NEW.pay_time IS NOT NULL THEN
    INSERT INTO sales_daily (stat_date, order_count, ticket_count, total_amount)
    VALUES (DATE(NEW.pay_time), 1, NEW.ticket_count, NEW.total_amount)
    ON DUPLICATE KEY UPDATE
      order_count  = order_count  + 1,
      ticket_count = ticket_count + NEW.ticket_count,
      total_amount = total_amount + NEW.total_amount;
  END IF;
END//
DROP TRIGGER IF EXISTS trg_order_paid//
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
DROP EVENT IF EXISTS ev_session_status//
CREATE EVENT ev_session_status
ON SCHEDULE EVERY 1 MINUTE
  STARTS CURRENT_TIMESTAMP
COMMENT '自动推进演出场次售票状态'
DO
BEGIN
  -- 1. 已过开演时间的场次推进为 4 (已结束)
  UPDATE show_session se
  SET se.sale_status = 4
  WHERE se.show_time <= NOW() AND se.sale_status <> 4;

  -- 2. 未来场次无余票的推进为 3 (已售罄)
  UPDATE show_session se
  SET se.sale_status = 3
  WHERE se.show_time > NOW()
    AND EXISTS (SELECT 1 FROM ticket_tier t WHERE t.session_id = se.session_id)
    AND NOT EXISTS (
          SELECT 1 FROM ticket_tier t
          WHERE t.session_id = se.session_id
            AND t.total_seats - t.sold_seats > 0
        )
    AND se.sale_status <> 3;

  -- 3. 到达开售时间且有余票的未来场次推进为 2 (售票中)
  UPDATE show_session se
  SET se.sale_status = 2
  WHERE se.show_time > NOW()
    AND se.sale_start <= NOW()
    AND (NOT EXISTS (SELECT 1 FROM ticket_tier t WHERE t.session_id = se.session_id)
         OR EXISTS (SELECT 1 FROM ticket_tier t
                    WHERE t.session_id = se.session_id AND t.total_seats > t.sold_seats))
    AND se.sale_status <> 2;

  -- 4. 未到开售时间的未来场次维持/置为 1 (预售中)
  UPDATE show_session se
  SET se.sale_status = 1
  WHERE se.show_time > NOW()
    AND se.sale_start > NOW()
    AND (NOT EXISTS (SELECT 1 FROM ticket_tier t WHERE t.session_id = se.session_id)
         OR EXISTS (SELECT 1 FROM ticket_tier t
                    WHERE t.session_id = se.session_id AND t.total_seats > t.sold_seats))
    AND se.sale_status <> 1;
END//
DELIMITER ;

SET GLOBAL event_scheduler = ON;
