-- ============================================================================
-- 演出门票销售系统 测试数据脚本 (MySQL 8.0)
-- 执行顺序：先 ddl.sql 建库，再运行本脚本。
-- 内容：字典补充 / 场馆 / 管理员 / 演出 / 图片 / 场次 / 票档 /
--       用户 / 收货信息 / 购票人 / 订单 / 明细 / 购票请求 / 汇总刷新 /
--       售票状态自动推进事件 / （可选）10 万用户批量生成。
-- 口令说明：password_hash 为 bcrypt 占位串，纯 SQL 测试无需校验；
--   如需真实登录，请在应用环境执行后替换：
--   python -c "import bcrypt;print(bcrypt.hashpw(b'123456',bcrypt.gensalt()).decode())"
-- ============================================================================
USE ticket_sales;

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE purchase_request;
TRUNCATE TABLE order_item;
TRUNCATE TABLE ticket_order;
TRUNCATE TABLE attendee;
TRUNCATE TABLE shipping_address;
TRUNCATE TABLE ticket_tier;
TRUNCATE TABLE show_session;
TRUNCATE TABLE show_image;
TRUNCATE TABLE show_item;
TRUNCATE TABLE venue;
TRUNCATE TABLE app_user;
TRUNCATE TABLE admin;
TRUNCATE TABLE sales_daily;
SET FOREIGN_KEY_CHECKS = 1;

-- ----------------------------------------------------------------------------
-- 一、城市（ddl 已插入 8 个，这里补充到 12 个；INSERT IGNORE 避免重复）
-- ----------------------------------------------------------------------------
INSERT IGNORE INTO city (city_id, city_name) VALUES
  (9,'南京'),(10,'重庆'),(11,'长沙'),(12,'天津');

-- 演出类型 ddl 已插入 7 种，此处不再重复。

-- ----------------------------------------------------------------------------
-- 二、管理员（用户名 admin；口令占位，正式环境替换为 bcrypt 哈希）
-- ----------------------------------------------------------------------------
INSERT INTO admin (admin_id, username, password_hash, real_name, role) VALUES
  (1, 'admin',
   '$2b$10$0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ',
   '系统管理员', 9);

-- ----------------------------------------------------------------------------
-- 三、场馆
-- ----------------------------------------------------------------------------
INSERT INTO venue (venue_id, city_id, venue_name, address, capacity) VALUES
  (1,  1, '国家体育场（鸟巢）',       '北京市朝阳区国家体育场南路1号',   90000),
  (2,  1, '北京工人体育场',           '北京市朝阳区工人体育场北路',      65000),
  (3,  2, '梅赛德斯-奔驰文化中心',    '上海市浦东新区世博大道1200号',    18000),
  (4,  2, '上海大剧院',               '上海市黄浦区人民大道300号',       1600),
  (5,  3, '广州天河体育馆',           '广州市天河区天河路299号',         10000),
  (6,  4, '深圳湾体育中心体育馆',     '深圳市南山区滨海大道3001号',      20000),
  (7,  5, '杭州黄龙体育中心体育场',   '杭州市西湖区黄龙路1号',           52000),
  (8,  6, '成都东安湖体育中心体育馆', '成都市龙泉驿区双龙路',           18000),
  (9,  7, '武汉琴台大剧院',           '武汉市汉阳区知音大道7号',         1800),
  (10, 8, '西安奥体中心体育场',       '西安市灞桥区奥体大道',            60000),
  (11, 1, '北京保利剧院',             '北京市东城区东直门南大街14号',    1500),
  (12, 4, '深圳市少年宫剧场',         '深圳市福田区福中一路2002号',      1200),
  (13, 2, '上海西岸艺术中心',         '上海市徐汇区龙腾大道2555号',      5000),
  (14, 5, '杭州大剧院',               '杭州市江干区新业路39号',          1600),
  (15, 6, '成都城市音乐厅',           '成都市武侯区一环路南一段47号',    1800);

-- ----------------------------------------------------------------------------
-- 四、演出（8 个，覆盖 5+ 种类型、多个城市）
-- ----------------------------------------------------------------------------
INSERT INTO show_item (show_id, show_name, category_id, city_id, poster_url, description, admin_id) VALUES
  (1,'周杰伦《嘉年华》世界巡回演唱会', 1, 1,'/static/img/concert1.jpg',
   '周杰伦《嘉年华》世界巡回演唱会，经典曲目全新编排，豪华舞美呈现，带你重温青春记忆。',1),
  (2,'张学友《60+》巡回演唱会',        1, 2,'/static/img/concert2.jpg',
   '歌神张学友 60+ 巡演，一连两晚，数十首经典金曲，现场交响乐团编制。',1),
  (3,'话剧《雷雨》',                   2, 1,'/static/img/theater1.jpg',
   '曹禺经典话剧《雷雨》，北京人民艺术剧院班底演出，两个场景、一天之内、三十年恩怨。',1),
  (4,'CBA 常规赛：广东宏远 vs 辽宁本钢',3, 3,'/static/img/basket1.jpg',
   'CBA 常规赛焦点战，华南虎对阵东北虎，强强对话一票难求。',1),
  (6,'莫奈《光影》沉浸式艺术展',       5, 2,'/static/img/museum1.jpg',
   '莫奈《光影》沉浸式数字艺术展，3000 平米投影空间，重现睡莲与日出印象。',1),
  (7,'郎朗钢琴独奏音乐会',             6, 5,'/static/img/piano1.jpg',
   '国际钢琴大师郎朗独奏音乐会，曲目涵盖巴赫、肖邦、拉威尔与中国作品。',1),
  (8,'舞剧《只此青绿》',               7, 6,'/static/img/dance1.jpg',
   '现象级舞剧《只此青绿》，以《千里江山图》为灵感，东方美学巅峰之作。',1);

-- ----------------------------------------------------------------------------
-- 五、演出介绍图片（每场 2-3 张）
-- ----------------------------------------------------------------------------
INSERT INTO show_image (show_id, image_url, sort_no) VALUES
  (1,'/static/img/concert1.jpg',1),(1,'/static/img/concert2.jpg',2),(1,'/static/img/concert3.jpg',3),
  (2,'/static/img/concert2.jpg',1),(2,'/static/img/concert3.jpg',2),
  (3,'/static/img/theater1.jpg',1),(3,'/static/img/theater2.jpg',2),
  (4,'/static/img/basket1.jpg',1),(4,'/static/img/basket2.jpg',2),
  (6,'/static/img/museum1.jpg',1),(6,'/static/img/theater2.jpg',2),
  (7,'/static/img/piano1.jpg',1),(7,'/static/img/piano2.jpg',2),
  (8,'/static/img/dance1.jpg',1),(8,'/static/img/dance2.jpg',2);

-- ----------------------------------------------------------------------------
-- 六、演出场次（开售时间统一早于开演时间 30 天）
--   2=售票中、1=预售中、3=未来场次售罄、4=已结束。
-- ----------------------------------------------------------------------------
INSERT INTO show_session (session_id, show_id, venue_id, show_time, sale_start, sale_status) VALUES
  (1, 1, 1,  TIMESTAMP(DATE(DATE_ADD(NOW(), INTERVAL 5 DAY)), '19:30:00'),  TIMESTAMP(DATE(DATE_SUB(NOW(), INTERVAL 25 DAY)), '19:30:00'), 2), -- 周杰伦 售票中
  (2, 1, 1,  TIMESTAMP(DATE(DATE_ADD(NOW(), INTERVAL 60 DAY)), '20:00:00'), TIMESTAMP(DATE(DATE_ADD(NOW(), INTERVAL 30 DAY)), '20:00:00'), 1), -- 周杰伦 预售中
  (3, 2, 3,  TIMESTAMP(DATE(DATE_ADD(NOW(), INTERVAL 20 DAY)), '19:00:00'), TIMESTAMP(DATE(DATE_SUB(NOW(), INTERVAL 10 DAY)), '19:00:00'), 2), -- 张学友 第一场
  (4, 2, 3,  TIMESTAMP(DATE(DATE_ADD(NOW(), INTERVAL 75 DAY)), '19:30:00'), TIMESTAMP(DATE(DATE_ADD(NOW(), INTERVAL 45 DAY)), '19:30:00'), 1), -- 张学友 第二场（预售）
  (5, 3, 11, TIMESTAMP(DATE(DATE_ADD(NOW(), INTERVAL 15 DAY)), '19:30:00'), TIMESTAMP(DATE(DATE_SUB(NOW(), INTERVAL 15 DAY)), '19:30:00'), 3), -- 雷雨 首场(售罄)
  (6, 3, 11, TIMESTAMP(DATE(DATE_ADD(NOW(), INTERVAL 90 DAY)), '14:30:00'), TIMESTAMP(DATE(DATE_ADD(NOW(), INTERVAL 60 DAY)), '14:30:00'), 1), -- 雷雨 加场(预售中)
  (7, 4, 5,  TIMESTAMP(DATE(DATE_SUB(NOW(), INTERVAL 3 DAY)), '19:35:00'),  TIMESTAMP(DATE(DATE_SUB(NOW(), INTERVAL 33 DAY)), '19:35:00'), 4), -- CBA 已结束
  (10,6, 13, TIMESTAMP(DATE(DATE_SUB(NOW(), INTERVAL 7 DAY)), '10:00:00'),  TIMESTAMP(DATE(DATE_SUB(NOW(), INTERVAL 37 DAY)), '10:00:00'), 4), -- 莫奈展 已结束
  (11,7, 14, TIMESTAMP(DATE(DATE_SUB(NOW(), INTERVAL 3 DAY)), '19:30:00'),  TIMESTAMP(DATE(DATE_SUB(NOW(), INTERVAL 33 DAY)), '19:30:00'), 4), -- 郎朗 已结束
  (12,8, 15, TIMESTAMP(DATE(DATE_SUB(NOW(), INTERVAL 21 DAY)), '19:30:00'), TIMESTAMP(DATE(DATE_SUB(NOW(), INTERVAL 51 DAY)), '19:30:00'), 4), -- 只此青绿 已结束
  (13,8, 15, TIMESTAMP(DATE(DATE_SUB(NOW(), INTERVAL 5 DAY)), '14:00:00'),  TIMESTAMP(DATE(DATE_SUB(NOW(), INTERVAL 35 DAY)), '14:00:00'), 4); -- 只此青绿 已结束

-- ----------------------------------------------------------------------------
-- 七、票档（tier_id 显式给出，方便订单引用）
--   se5(雷雨首场) 三档全部 sold=total => 售罄；
--   se1 的 1980 档 sold=total => 详情页显示"该票档售罄"。
-- ----------------------------------------------------------------------------
INSERT INTO ticket_tier (tier_id, session_id, tier_name, price, total_seats, sold_seats) VALUES
  -- se1 周杰伦（售票中，内场售罄）
  (1, 1,'内场 1980',1980.00, 2000, 2000),
  (2, 1,'看台 980',  980.00, 8000, 6500),
  (3, 1,'看台 580',  580.00,10000, 4200),
  (4, 1,'看台 380',  380.00,15000, 3000),
  -- se2 周杰伦（预售中，未开票）
  (5, 2,'内场 1980',1980.00, 2000,    0),
  (6, 2,'看台 980',  980.00, 8000,    0),
  (7, 2,'看台 580',  580.00,10000,    0),
  (8, 2,'看台 380',  380.00,15000,    0),
  -- se3 张学友第一场
  (9, 3,'内场 1980',1980.00, 1800, 1700),
  (10,3,'看台 1680',1680.00, 3000, 2800),
  (11,3,'看台 980',  980.00, 6000, 4100),
  (12,3,'看台 580',  580.00, 7000, 2000),
  -- se4 张学友第二场
  (13,4,'内场 1980',1980.00, 1800,  900),
  (14,4,'看台 1680',1680.00, 3000, 1200),
  (15,4,'看台 980',  980.00, 6000,  800),
  (16,4,'看台 580',  580.00, 7000,  100),
  -- se5 雷雨首场（全部售罄）
  (17,5,'VIP 880',  880.00, 300, 300),
  (18,5,'一等 580', 580.00, 500, 500),
  (19,5,'二等 380', 380.00, 700, 700),
  -- se6 雷雨加场（预售中）
  (20,6,'VIP 880',  880.00, 300,   0),
  (21,6,'一等 580', 580.00, 500,   0),
  (22,6,'二等 380', 380.00, 700,   0),
  -- se7 CBA
  (23,7,'特等 1280',1280.00,1000, 800),
  (24,7,'一等 680',  680.00,2000,1500),
  (25,7,'二等 380',  380.00,3000, 900),
  (26,7,'三等 180',  180.00,4000, 200),
  -- se10 莫奈展
  (35,10,'VIP 导览票 498',498.00, 500,120),
  (36,10,'通票 298',      298.00,1500,980),
  (37,10,'平日票 198',    198.00,2000,600),
  -- se11 郎朗
  (38,11,'VIP 1280',1280.00,200,190),
  (39,11,'一等 880',  880.00,400,350),
  (40,11,'二等 480',  480.00,600,210),
  (41,11,'三等 280',  280.00,400, 60),
  -- se12 只此青绿（预售中）
  (42,12,'VIP 880',  880.00,300,  0),
  (43,12,'一等 680', 680.00,500,  0),
  (44,12,'二等 480', 480.00,600,  0),
  (45,12,'三等 280', 280.00,400,  0),
  -- se13 只此青绿（售票中，接近售罄）
  (46,13,'VIP 880',  880.00,300,290),
  (47,13,'一等 680', 680.00,500,480),
  (48,13,'二等 480', 480.00,600,300),
  (49,13,'三等 280', 280.00, 400, 80);

-- ----------------------------------------------------------------------------
-- 八、用户（5 个测试用户；10 万批量生成见文末附录）
-- ----------------------------------------------------------------------------
INSERT INTO app_user (user_id, username, password_hash, phone, email, status) VALUES
  (1,'zhang_san','$2b$10$0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ','13800000001','zhangsan@example.com',1),
  (2,'li_si',    '$2b$10$0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ','13800000002','lisi@example.com',    1),
  (3,'wang_wu',  '$2b$10$0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ','13800000003','wangwu@example.com',  1),
  (4,'zhao_liu', '$2b$10$0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ','13800000004','zhaoliu@example.com', 1),
  (5,'chen_qi',  '$2b$10$0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ','13800000005','chenqi@example.com',  1);

-- ----------------------------------------------------------------------------
-- 九、收货信息
-- ----------------------------------------------------------------------------
INSERT INTO shipping_address (address_id, user_id, receiver_name, phone, address_detail, is_default) VALUES
  (1,1,'张三','13800000001','北京市海淀区中关村大街1号',          1),
  (2,1,'李梅','13800000011','北京市朝阳区建国路88号SOHO现代城',   0),
  (3,2,'李四','13800000003','上海市浦东新区世纪大道100号',        1),
  (4,3,'王五','13800000004','广州市天河区天河路208号',            1),
  (5,4,'赵六','13800000005','杭州市西湖区文三路50号',             1),
  (6,5,'陈七','13800000006','成都市武侯区天府大道1000号',         1);

-- ----------------------------------------------------------------------------
-- 十、常用购票人（证件号为演示用假数据）
-- ----------------------------------------------------------------------------
INSERT INTO attendee (attendee_id, user_id, attendee_name, id_type, id_no) VALUES
  (1, 1,'张三',   1,'110101199001011234'),
  (2, 1,'李梅',   1,'110101199203054567'),
  (3, 1,'张小明', 1,'11010120150607678X'),
  (4, 2,'李四',   1,'310104198802023456'),
  (5, 2,'王芳',   1,'310104199005127890'),
  (6, 3,'王五',   1,'440106199511112222'),
  (7, 4,'赵六',   1,'330103198707073333'),
  (8, 4,'赵乐乐', 1,'330103201601028888'),
  (9, 5,'陈七',   1,'510107199209094444'),
  (10,5,'陈八',   2,'510107198812125555');  -- 护照

-- ----------------------------------------------------------------------------
-- 十一、订单（o1-o7 已支付；o8 待支付；o9 已取消）
-- ----------------------------------------------------------------------------
INSERT INTO ticket_order
  (order_id, order_no, user_id, session_id, tier_id, address_id,
   ticket_count, total_amount, order_status, create_time, pay_time) VALUES
  (1,'NO20250101001',1, 1, 2, 1, 2, 1960.00, 2, DATE_SUB(NOW(),INTERVAL 2 DAY), DATE_SUB(NOW(),INTERVAL 2 DAY)),
  (2,'NO20250102001',2, 3,11, 3, 2, 1960.00, 2, DATE_SUB(NOW(),INTERVAL 3 DAY), DATE_SUB(NOW(),INTERVAL 3 DAY)),
  (3,'NO20250103001',1, 1, 3, 1, 3, 1740.00, 2, DATE_SUB(NOW(),INTERVAL 5 DAY), DATE_SUB(NOW(),INTERVAL 5 DAY)),
  (4,'NO20250104001',3, 7,25, 4, 1,  380.00, 2, DATE_SUB(NOW(),INTERVAL 5 DAY), DATE_SUB(NOW(),INTERVAL 5 DAY)),
  (5,'NO20250105001',4,11,39, 5, 2, 1760.00, 2, DATE_SUB(NOW(),INTERVAL 4 DAY), DATE_SUB(NOW(),INTERVAL 4 DAY)),
  (6,'NO20250106001',5,13,47, 6, 2, 1360.00, 2, DATE_SUB(NOW(),INTERVAL 6 DAY), DATE_SUB(NOW(),INTERVAL 6 DAY)),
  (7,'NO20250107001',2,10,36, 3, 1,  298.00, 2, DATE_SUB(NOW(),INTERVAL 8 DAY), DATE_SUB(NOW(),INTERVAL 8 DAY)),
  (8,'NO20250108001',3, 1, 3, 4, 1,  580.00, 1, DATE_SUB(NOW(),INTERVAL 1 DAY), NULL),
  (9,'NO20250109001',4, 4,16, 5, 1,  580.00, 3, DATE_SUB(NOW(),INTERVAL 10 DAY), NULL);

-- 十二、订单明细（每张票绑定一位购票人；注意 (attendee_id, session_id) 唯一）
INSERT INTO order_item (order_id, tier_id, attendee_id, session_id, unit_price) VALUES
  (1, 2, 1, 1, 980.00),   -- o1 张三 周杰伦 看台980
  (1, 2, 2, 1, 980.00),   -- o1 李梅
  (2,11, 4, 3, 980.00),   -- o2 李四 张学友
  (2,11, 5, 3, 980.00),   -- o2 王芳
  (3, 3, 3, 1, 580.00),   -- o3 张三一家 周杰伦 看台580
  (3, 3, 7, 1, 580.00),
  (3, 3, 8, 1, 580.00),
  (4,25, 6, 7, 380.00),   -- o4 王五 CBA
  (5,39, 7,11, 880.00),   -- o5 赵六父子 郎朗
  (5,39, 8,11, 880.00),
  (6,47, 9,13, 680.00),   -- o6 陈七姐弟 只此青绿
  (6,47,10,13, 680.00),
  (7,36, 4,10, 298.00),   -- o7 李四 莫奈展
  (8, 3, 6, 1, 580.00),   -- o8 待支付
  (9,16, 7, 4, 580.00);   -- o9 已取消

-- ----------------------------------------------------------------------------
-- 十三、购票请求日志（成功 + 各类失败，验证"所有请求都记录"）
-- ----------------------------------------------------------------------------
INSERT INTO purchase_request
  (user_id, session_id, tier_id, ticket_count, result, fail_reason, request_time) VALUES
  (1, 1, 2, 2, 1, NULL,                                          DATE_SUB(NOW(),INTERVAL 2 DAY)),
  (2, 3,11, 2, 1, NULL,                                          DATE_SUB(NOW(),INTERVAL 3 DAY)),
  (1, 1, 3, 3, 1, NULL,                                          DATE_SUB(NOW(),INTERVAL 5 DAY)),
  (3, 7,25, 1, 1, NULL,                                          DATE_SUB(NOW(),INTERVAL 1 DAY)),
  (5,13,47, 2, 1, NULL,                                          DATE_SUB(NOW(),INTERVAL 6 DAY)),
  (1, 5,17, 2, 0, '余票不足：该场次已售罄',                       DATE_SUB(NOW(),INTERVAL 1 DAY)),
  (1, 1, 2, 1, 0, '超出限购：购票人张三已购买该场次门票',         DATE_SUB(NOW(),INTERVAL 1 DAY)),
  (4,12,42, 2, 0, '演出尚未开售（预售中）',                      DATE_SUB(NOW(),INTERVAL 2 DAY)),
  (2, 3, 9, 4, 0, '余票不足：内场1980档余票不足4张',             DATE_SUB(NOW(),INTERVAL 2 DAY));

-- ----------------------------------------------------------------------------
-- 十四、刷新销售日汇总（与已支付订单保持一致；日常由触发器自动维护）
-- ----------------------------------------------------------------------------
TRUNCATE TABLE sales_daily;
INSERT INTO sales_daily (stat_date, order_count, ticket_count, total_amount)
SELECT DATE(pay_time), COUNT(*), SUM(ticket_count), SUM(total_amount)
FROM ticket_order
WHERE order_status = 2 AND pay_time IS NOT NULL
GROUP BY DATE(pay_time);

-- ----------------------------------------------------------------------------
-- 十五、售票状态自动推进事件（每 10 分钟，属于物化状态维护）
--   事件只会关闭已结束/无余票场次，不会把预售站点批量提升为在售，
--   以免破坏“每个系列最多一个在售站”的约束。新增数据后运行
--   scripts/data/rebalance_status.py 选择新的在售站点。
--   SET GLOBAL event_scheduler = ON。
-- ----------------------------------------------------------------------------
DELIMITER //
DROP EVENT IF EXISTS ev_session_status//
CREATE EVENT ev_session_status
ON SCHEDULE EVERY 10 MINUTE
  STARTS CURRENT_TIMESTAMP
COMMENT '自动推进演出场次售票状态'
DO
BEGIN
  -- 已结束场次与卖完的未来场次使用不同状态。
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

-- 查看事件：SHOW EVENTS;  手动验证可直接执行上述两条 UPDATE。

-- ============================================================================
-- 附录（可选）：批量生成 10 万用户，验证大数据量
--   取消注释后整段执行；MySQL 8 递归 CTE 默认上限 1000，需先调大。
-- ----------------------------------------------------------------------------
/*
SET SESSION cte_max_recursion_depth = 100000;

INSERT INTO app_user (username, password_hash, phone, email, status)
WITH RECURSIVE seq(k) AS (
  SELECT 1
  UNION ALL
  SELECT k + 1 FROM seq WHERE k < 100000
)
SELECT CONCAT('bulk_user', LPAD(k, 6, '0')),
       '$2b$10$0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ',
       CONCAT('139', LPAD(k, 8, '0')),                -- 139 + 8 位 = 11 位手机号
       CONCAT('bulk', k, '@example.com'),
       1
FROM seq;

-- 验证：SELECT COUNT(*) FROM app_user;   -- 应为 100005
*/
