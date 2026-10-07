-- Upgrade existing databases to distinguish sold-out from ended sessions.
-- This migration does not drop or recreate ticket_sales.
USE ticket_sales;

ALTER TABLE show_session
  MODIFY sale_status TINYINT NOT NULL DEFAULT 1
  COMMENT '1预售中 2售票中 3售罄 4已结束';

-- Keep release times in chronological order with show times.
UPDATE show_session
SET sale_start = DATE_SUB(show_time, INTERVAL 30 DAY);

UPDATE show_session
SET sale_status = 4
WHERE show_time <= NOW();

UPDATE show_session se
SET se.sale_status = 3
WHERE se.show_time > NOW()
  AND EXISTS (SELECT 1 FROM ticket_tier t WHERE t.session_id = se.session_id)
  AND NOT EXISTS (
    SELECT 1 FROM ticket_tier t
    WHERE t.session_id = se.session_id
      AND t.total_seats - t.sold_seats > 0
  );

DELIMITER //
DROP EVENT IF EXISTS ev_session_status//
CREATE EVENT ev_session_status
ON SCHEDULE EVERY 10 MINUTE
  STARTS CURRENT_TIMESTAMP
COMMENT '自动推进演出场次售票状态'
DO
BEGIN
  UPDATE show_session se
  SET se.sale_status = 4
  WHERE se.show_time <= NOW();

  UPDATE show_session se
  SET se.sale_status = 3
  WHERE se.show_time > NOW()
    AND EXISTS (SELECT 1 FROM ticket_tier t WHERE t.session_id = se.session_id)
    AND NOT EXISTS (
      SELECT 1 FROM ticket_tier t
      WHERE t.session_id = se.session_id
        AND t.total_seats - t.sold_seats > 0
    );
END//
DELIMITER ;

-- Run sql/schema/views.sql after this migration to refresh v_show_list.
