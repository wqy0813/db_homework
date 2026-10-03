-- ============================================================================
-- 第 4 期：巡演/IP 三层聚合模型
--   巡演 show_series（IP/巡演，含主演）→ 城市站 show_item（新增 series_id）→ 场次 show_session
--   说明：show_series 聚合"同一个巡演/剧目"的多个城市站，首页按巡演展示，
--         点进去展开各城市站；主演照片存在 series 上（有区分度）。
-- ============================================================================
USE ticket_sales;

-- 1) 巡演/IP 表（1 个巡演 = 1 行）
CREATE TABLE IF NOT EXISTS show_series (
  series_id     INT          NOT NULL AUTO_INCREMENT COMMENT '巡演ID',
  series_name   VARCHAR(100) NOT NULL COMMENT '巡演/IP名称（如 周杰伦《嘉年华》世界巡回演唱会）',
  category_id   TINYINT      NOT NULL COMMENT '类型',
  main_artist   VARCHAR(50)  DEFAULT NULL COMMENT '主演/歌手（用于海报区分度）',
  poster_url    VARCHAR(255) DEFAULT NULL COMMENT '巡演海报（主演照片）',
  description   TEXT         COMMENT '巡演介绍',
  create_time   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (series_id),
  UNIQUE KEY uk_series_name (series_name),
  KEY idx_series_cat (category_id),
  CONSTRAINT fk_series_cat FOREIGN KEY (category_id) REFERENCES category (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='巡演/IP表';

-- 2) show_item 增加 series_id（指向所属巡演；可空=未归属）。
--    ddl.sql 已包含这些对象；这里保留为可重复执行的升级脚本，兼容旧库。
DELIMITER //
DROP PROCEDURE IF EXISTS _phase4_upgrade//
CREATE PROCEDURE _phase4_upgrade()
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema = DATABASE() AND table_name = 'show_item'
       AND column_name = 'series_id'
  ) THEN
    ALTER TABLE show_item ADD COLUMN series_id INT DEFAULT NULL AFTER city_id;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.statistics
     WHERE table_schema = DATABASE() AND table_name = 'show_item'
       AND index_name = 'idx_show_series'
  ) THEN
    ALTER TABLE show_item ADD KEY idx_show_series (series_id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.referential_constraints
     WHERE constraint_schema = DATABASE() AND table_name = 'show_item'
       AND constraint_name = 'fk_show_series'
  ) THEN
    ALTER TABLE show_item ADD CONSTRAINT fk_show_series
      FOREIGN KEY (series_id) REFERENCES show_series (series_id);
  END IF;
END//
CALL _phase4_upgrade()//
DROP PROCEDURE _phase4_upgrade//
DELIMITER ;
