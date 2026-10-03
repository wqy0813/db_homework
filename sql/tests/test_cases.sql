-- ============================================================================
-- 演出门票销售系统 人工测试脚本 (MySQL 8.0 / Navicat)
-- 用法：
--   1) 先依次执行 ddl.sql、seed_data.sql；
--   2) Navicat 中打开本文件，按【TC-xx】分节逐段执行（选中一段点运行）；
--   3) 每节注释里写明了【预期结果】，对照核对即可；
--   4) 出错时看 Navicat 底部“信息”栏的错误号：
--        1062 = 唯一约束冲突（重复）   1452 = 外键约束冲突
--        3819 = CHECK 约束冲突        1264/... = 其他
--   5) 凡以 START TRANSACTION 开头的用例，最后若不 COMMIT，务必执行 ROLLBACK;
-- 约定：可重复执行（购票成功用例会新建购票人/订单号，多次跑不冲突）。
-- ============================================================================
USE ticket_sales;

-- ############################################################################
-- 模块一：登录（游客功能）
-- ############################################################################

-- TC-01 用户登录【成功】：输入正确用户名，返回用户记录与口令哈希
-- 预期：返回 1 行，username=zhang_san，status=1（应用层再做 bcrypt 校验）
SELECT user_id, username, password_hash, status
FROM app_user
WHERE username = 'zhang_san';

-- TC-02 用户登录【失败-用户不存在】
-- 预期：返回 0 行（应用层据此提示“用户名或密码错误”）
SELECT user_id, username, password_hash, status
FROM app_user
WHERE username = 'no_such_user';

-- TC-03 管理员登录
-- 预期：返回 1 行，username=admin，role=9（超级管理员）
SELECT admin_id, username, password_hash, role
FROM admin
WHERE username = 'admin';

-- ############################################################################
-- 模块二：游客——演出列表
-- ############################################################################

-- TC-04 演出列表【全部】
-- 预期：8 行；每行含 名称/城市/类型/场馆(地点)/最近日期/最低价/最高价/状态
SELECT * FROM v_show_list ORDER BY show_id;

-- TC-05 演出列表【按城市筛选：北京 city_id=1】
-- 预期：2 行——周杰伦演唱会(北京)、话剧雷雨(北京)
SELECT * FROM v_show_list WHERE city_id = 1 ORDER BY show_id;

-- TC-06 演出列表【按类型筛选：演唱会 category_id=1】
-- 预期：2 行——周杰伦、张学友
SELECT * FROM v_show_list WHERE category_id = 1 ORDER BY show_id;

-- TC-07 演出列表【城市+类型组合：上海(2) + 展览(5)】
-- 预期：1 行——莫奈《光影》沉浸式艺术展
SELECT * FROM v_show_list WHERE city_id = 2 AND category_id = 5;

-- TC-08 列表字段核对【票价区间与售票状态】
-- 预期：周杰伦 min_price=380.00 max_price=1980.00、状态“售票中”；
--       雷雨(show 3) 首场售罄但加场预售中，按聚合规则
--       “有售票中→2；否则有预售中→1；全售罄→3”，show_status=1（预售中），属正确；
--       所有行状态文本无 NULL。
SELECT show_id, show_name, min_price, max_price, show_status,
       ELT(show_status, '预售中', '售票中', '售罄') AS status_text
FROM v_show_list ORDER BY show_id;

-- ############################################################################
-- 模块三：游客——演出详情
-- ############################################################################

-- TC-09 演出详情【基本信息：周杰伦 show_id=1】
-- 预期：名称、海报、介绍文字、城市=北京、类型=演唱会、价格 380~1980
SELECT s.show_id, s.show_name, s.poster_url, s.description,
       c.city_name, cat.category_name,
       (SELECT MIN(price) FROM ticket_tier t
          JOIN show_session se ON se.session_id=t.session_id WHERE se.show_id=s.show_id) AS min_price,
       (SELECT MAX(price) FROM ticket_tier t
          JOIN show_session se ON se.session_id=t.session_id WHERE se.show_id=s.show_id) AS max_price
FROM show_item s
JOIN city c ON c.city_id=s.city_id
JOIN category cat ON cat.category_id=s.category_id
WHERE s.show_id = 1;

-- TC-10 演出介绍图片【多张】
-- 预期：show 1 返回 3 行（jay_1/jay_2/jay_3），按 sort_no 排序
SELECT image_url, sort_no FROM show_image
WHERE show_id = 1 ORDER BY sort_no;

-- TC-11 演出日期列表【若干场次】
-- 预期：周杰伦 2 个场次（30 天后售票中、60 天后预售中）；
--       海底小纵队 2 个场次。地点(场馆)随之显示。
SELECT se.session_id, se.show_time, v.venue_name, v.address,
       ELT(se.sale_status,'预售中','售票中','售罄') AS status_text
FROM show_session se
JOIN venue v ON v.venue_id=se.venue_id
WHERE se.show_id = 1 ORDER BY se.show_time;

-- TC-12 票档列表与售罄标记【核心展示】
-- 预期：session 1（周杰伦）4 档：内场1980 remain_seats=0 sold_out=1（显示“该票档售罄”），
--       其余 3 档有余票 sold_out=0；
--       session 5（雷雨首场）3 档全部 sold_out=1。
SELECT tier_id, tier_name, price, total_seats, sold_seats, remain_seats,
       CASE WHEN sold_out=1 THEN '该票档售罄' ELSE '在售' END AS display
FROM v_tier_stock WHERE session_id = 1 ORDER BY price DESC;

SELECT tier_id, tier_name, price, remain_seats,
       CASE WHEN sold_out=1 THEN '该票档售罄' ELSE '在售' END AS display
FROM v_tier_stock WHERE session_id = 5 ORDER BY price DESC;

-- ############################################################################
-- 模块四：用户——购票（核心事务）
-- ############################################################################

-- TC-13 购票【成功完整流程】
-- 场景：用户 1(张三) 购买 session 1(周杰伦) / tier 3(看台580) 1 张，
--       使用一位“新购票人”（脚本自动新建，证件号带时间戳，可重复执行）。
START TRANSACTION;

-- 购票前余票（记住 sold_seats，购票后应 +1）
SELECT tier_id, total_seats, sold_seats,
       total_seats-sold_seats AS remain_before
FROM ticket_tier WHERE tier_id = 3;

-- ① 记录购票请求（先落库，结果待定）
INSERT INTO purchase_request(user_id, session_id, tier_id, ticket_count, result, fail_reason)
VALUES (1, 1, 3, 1, 0, '处理中');
SET @req_id = LAST_INSERT_ID();

-- ② 原子扣减余票（影响行数=1 才成功）
UPDATE ticket_tier
SET sold_seats = sold_seats + 1
WHERE tier_id = 3 AND total_seats - sold_seats >= 1;
SELECT ROW_COUNT() AS deduct_affected;          -- 预期：1

-- ③ 新建本次购票人（证件号唯一，保证用例可重复跑）
INSERT INTO attendee(user_id, attendee_name, id_type, id_no)
SELECT 1, '测试购票人', 1, CONCAT('T', UNIX_TIMESTAMP(), FLOOR(RAND()*10000));
SET @att_id = LAST_INSERT_ID();

-- ④ 生成订单（金额=票档单价×票数）
INSERT INTO ticket_order
  (order_no, user_id, session_id, tier_id, address_id, ticket_count, total_amount, order_status)
SELECT CONCAT('T', UNIX_TIMESTAMP(), FLOOR(RAND()*1000)), 1, 1, 3, 1, 1, price, 1
FROM ticket_tier WHERE tier_id = 3;
SET @oid = LAST_INSERT_ID();

-- ⑤ 写明细：每张票绑定一位购票人
INSERT INTO order_item(order_id, tier_id, attendee_id, session_id, unit_price)
SELECT @oid, 3, @att_id, 1, price FROM ticket_tier WHERE tier_id = 3;

-- ⑥ 支付成功（触发器 trg_order_paid 自动累加 sales_daily）
UPDATE ticket_order SET order_status = 2, pay_time = NOW()
WHERE order_id = @oid;

-- ⑦ 请求日志回填成功
UPDATE purchase_request SET result = 1, fail_reason = NULL
WHERE request_id = @req_id;

COMMIT;

-- TC-13 验证（全部应与预期一致）：
SELECT sold_seats, total_seats-sold_seats AS remain_after
FROM ticket_tier WHERE tier_id = 3;                          -- sold_seats 较购票前 +1
SELECT * FROM ticket_order WHERE order_id = @oid;            -- order_status=2 已支付
SELECT oi.*, a.attendee_name FROM order_item oi
  JOIN attendee a ON a.attendee_id=oi.attendee_id
  WHERE oi.order_id = @oid;                                   -- 1 行，绑定新购票人
SELECT * FROM purchase_request WHERE request_id = @req_id;   -- result=1
SELECT * FROM sales_daily WHERE stat_date = CURDATE();        -- 今日订单数/票数/金额已累加

-- TC-14 购票【失败-余票不足】
-- 场景：购买 tier 1（内场1980，已售罄）。扣票 UPDATE 影响行数应为 0。
START TRANSACTION;
UPDATE ticket_tier
SET sold_seats = sold_seats + 1
WHERE tier_id = 1 AND total_seats - sold_seats >= 1;
SELECT ROW_COUNT() AS deduct_affected;          -- 预期：0（余票不足，购票失败）
ROLLBACK;
-- 失败请求同样留痕：
INSERT INTO purchase_request(user_id, session_id, tier_id, ticket_count, result, fail_reason)
VALUES (1, 1, 1, 1, 0, '余票不足：内场1980档已售罄（TC-14测试）');
-- 验证：tier 1 余票仍为 0，未发生超卖
SELECT tier_id, total_seats, sold_seats, total_seats-sold_seats AS remain
FROM ticket_tier WHERE tier_id = 1;                            -- 预期 remain=0

-- TC-15 购票【失败-超出限购】
-- 场景：attendee 1（张三）已购买 session 1 的票（种子订单 o1），
--       再为其购买同场次 → 明细唯一键冲突。
START TRANSACTION;
INSERT INTO ticket_order
  (order_no, user_id, session_id, tier_id, address_id, ticket_count, total_amount, order_status)
VALUES (CONCAT('LIMIT', UNIX_TIMESTAMP()), 1, 1, 3, 1, 1, 580.00, 1);
SET @oid2 = LAST_INSERT_ID();
-- 下一句预期报错：[Err] 1062 - Duplicate entry ... for key 'order_item.uk_item_attendee_session'
INSERT INTO order_item(order_id, tier_id, attendee_id, session_id, unit_price)
VALUES (@oid2, 3, 1, 1, 580.00);
-- 看到 1062 错误后，【务必单独选中下一句 ROLLBACK; 手动执行一次】
-- （Navicat 整段运行遇错会中止，ROLLBACK 不会自动跑到；不回滚会留下未提交的脏订单并持锁）：
ROLLBACK;
-- 验证：张三在 session 1 仍只有 1 张票（限购生效）
SELECT attendee_id, session_id, COUNT(*) AS tickets
FROM order_item
WHERE attendee_id = 1 AND session_id = 1
GROUP BY attendee_id, session_id;                -- 预期 tickets=1

-- ############################################################################
-- 模块五：用户——订单
-- ############################################################################

-- TC-16 我的订单列表【字段完整性】
-- 预期：用户 1 有 3 条订单（种子 2 条 + TC-13 新增 1 条），
--       每行含 订单号/演出名称/地点(城市+场馆)/演出日期/票数/金额/状态/收货信息
SELECT order_no, show_name,
       CONCAT(city_name, '·', venue_name) AS place,
       show_time, ticket_count, total_amount,
       ELT(order_status,'待支付','已支付','已取消','已退款') AS status_text,
       CONCAT(receiver_name,' ',phone,' ',address_detail) AS shipping
FROM v_order_detail
WHERE order_id IN (SELECT order_id FROM ticket_order WHERE user_id = 1)
ORDER BY create_time DESC;

-- TC-17 订单详情【每张票的持票人】
-- 预期：订单 1（周杰伦 2 张）返回 2 行：张三、李梅，单价 980
SELECT oi.item_id, oi.unit_price, a.attendee_name,
       ELT(a.id_type,'身份证','护照','港澳通行证','台胞证','军官证') AS id_type_name,
       a.id_no
FROM order_item oi
JOIN attendee a ON a.attendee_id = oi.attendee_id
WHERE oi.order_id = 1;

-- ############################################################################
-- 模块六：用户——收货信息管理
-- ############################################################################

-- TC-18 收货信息【新增】
INSERT INTO shipping_address(user_id, receiver_name, phone, address_detail, is_default)
VALUES (1, '测试收货人', '13900001111', '北京市西城区测试路99号（TC-18）', 0);
SET @addr_id = LAST_INSERT_ID();

-- TC-18b 收货信息【查询】预期：用户 1 共 3 条（原 2 + 新 1）
SELECT address_id, receiver_name, phone, address_detail, is_default
FROM shipping_address WHERE user_id = 1 ORDER BY is_default DESC, address_id;

-- TC-18c 收货信息【修改】
UPDATE shipping_address
SET receiver_name = '测试收货人-改', phone = '13900002222',
    address_detail = '北京市东城区修改路88号（TC-18改）'
WHERE address_id = @addr_id AND user_id = 1;
SELECT * FROM shipping_address WHERE address_id = @addr_id;   -- 预期显示修改后内容

-- TC-18d 收货信息【删除】
DELETE FROM shipping_address WHERE address_id = @addr_id AND user_id = 1;
SELECT COUNT(*) AS cnt FROM shipping_address WHERE address_id = @addr_id;  -- 预期 0

-- ############################################################################
-- 模块七：用户——常用购票人管理
-- ############################################################################

-- TC-19 购票人【新增】
INSERT INTO attendee(user_id, attendee_name, id_type, id_no)
VALUES (1, '测试购票人甲', 1, 'TESTCERT0001');
SET @new_att = LAST_INSERT_ID();

-- TC-19b 购票人【查询】预期：用户 1 原有 3 人(张三/李梅/张小明)+TC-13 新建+本用例
SELECT attendee_id, attendee_name,
       ELT(id_type,'身份证','护照','港澳通行证','台胞证','军官证') AS id_type_name,
       id_no
FROM attendee WHERE user_id = 1 ORDER BY attendee_id;

-- TC-20 购票人【证件重复约束】
-- 预期：[Err] 1062 Duplicate entry（同一用户证件类型+证件号唯一）
INSERT INTO attendee(user_id, attendee_name, id_type, id_no)
VALUES (1, '重复证件人', 1, '110101199001011234');   -- 与张三证件号相同

-- TC-21 购票人【被订单引用时删除-外键保护】
-- 预期：[Err] 1451 ... a foreign key constraint fails（删除被引用的父行；
--       注：1451=删除/更新父行被阻，1452=插入子行找不到父行，均属外键保护）
DELETE FROM attendee WHERE attendee_id = 1;

-- TC-22 购票人【删除未被引用的新建购票人】
DELETE FROM attendee WHERE attendee_id = @new_att;
SELECT COUNT(*) AS cnt FROM attendee WHERE attendee_id = @new_att;   -- 预期 0

-- ############################################################################
-- 模块八：管理员——演出信息管理
-- ############################################################################

-- TC-23 新建演出【名称/城市/类型/海报/介绍】
INSERT INTO show_item(show_name, category_id, city_id, poster_url, description, admin_id)
VALUES ('【测试】临时演唱会-可删除', 1, 7, '/img/poster/test.jpg',
        '这是一条用于管理员功能测试的临时演出，测试完成后删除。', 1);
SET @test_show = LAST_INSERT_ID();
SELECT * FROM show_item WHERE show_id = @test_show;

-- TC-24 添加场次【若干演出日期】
INSERT INTO show_session(show_id, venue_id, show_time, sale_start, sale_status) VALUES
  (@test_show, 9, DATE_ADD(NOW(), INTERVAL 35 DAY), DATE_SUB(NOW(), INTERVAL 1 DAY), 2),
  (@test_show, 9, DATE_ADD(NOW(), INTERVAL 36 DAY), DATE_ADD(NOW(), INTERVAL 8 DAY), 1);
-- 预期：该演出 2 个场次
SELECT session_id, show_time, sale_start, sale_status
FROM show_session WHERE show_id = @test_show;

-- TC-25 添加票档【若干档：名称/金额/票数】
INSERT INTO ticket_tier(session_id, tier_name, price, total_seats, sold_seats)
SELECT session_id, t.tier_name, t.price, t.total, 0
FROM show_session se
JOIN (
  SELECT 'VIP 1280' AS tier_name, 1280.00 AS price, 200 AS total
  UNION ALL SELECT '一等 880', 880.00, 500
  UNION ALL SELECT '二等 580', 580.00, 800
) t
WHERE se.show_id = @test_show;
-- 预期：2 场 × 3 档 = 6 个票档
SELECT t.tier_id, se.session_id, t.tier_name, t.price, t.total_seats
FROM ticket_tier t JOIN show_session se ON se.session_id=t.session_id
WHERE se.show_id = @test_show ORDER BY se.session_id, t.price DESC;

-- TC-26 添加演出图片【多张】
INSERT INTO show_image(show_id, image_url, sort_no) VALUES
  (@test_show, '/img/show/test_1.jpg', 1),
  (@test_show, '/img/show/test_2.jpg', 2);
SELECT COUNT(*) AS img_cnt FROM show_image WHERE show_id = @test_show;   -- 预期 2

-- TC-27 新演出在列表/详情中的展示
-- 预期：v_show_list 出现该演出，票价 580~1280，状态=2（有售票中场次）
SELECT show_id, show_name, min_price, max_price, show_status
FROM v_show_list WHERE show_id = @test_show;

-- TC-28 修改演出信息
UPDATE show_item SET show_name = '【测试】临时演唱会-已改名'
WHERE show_id = @test_show;
SELECT show_name FROM show_item WHERE show_id = @test_show;   -- 预期已改名

-- TC-29 删除演出【级联删除验证】
DELETE FROM show_item WHERE show_id = @test_show;
-- 预期：以下三个查询全部返回 0（场次/票档/图片随演出级联删除）
SELECT (SELECT COUNT(*) FROM show_session WHERE show_id=@test_show) AS sessions_left,
       (SELECT COUNT(*) FROM show_image   WHERE show_id=@test_show) AS images_left,
       (SELECT COUNT(*) FROM ticket_tier t JOIN show_session se ON se.session_id=t.session_id
        WHERE se.show_id=@test_show) AS tiers_left;

-- ############################################################################
-- 模块九：管理员——售票状态与销售统计
-- ############################################################################

-- TC-30 售票状态自动推进【模拟事件 ev_session_status 的逻辑】
-- 造两个测试场次：A 预售中但开售时间已过；B 售票中但票档全售罄
INSERT INTO show_session(show_id, venue_id, show_time, sale_start, sale_status)
VALUES (1, 1, DATE_ADD(NOW(),INTERVAL 70 DAY), DATE_SUB(NOW(),INTERVAL 1 MINUTE), 1);
SET @se_a = LAST_INSERT_ID();
INSERT INTO show_session(show_id, venue_id, show_time, sale_start, sale_status)
VALUES (1, 1, DATE_ADD(NOW(),INTERVAL 71 DAY), DATE_SUB(NOW(),INTERVAL 2 DAY), 2);
SET @se_b = LAST_INSERT_ID();
INSERT INTO ticket_tier(session_id, tier_name, price, total_seats, sold_seats)
VALUES (@se_b, '测试全售罄档', 100.00, 10, 10);

-- 执行与事件相同的两条推进语句：
UPDATE show_session SET sale_status = 2
WHERE sale_status = 1 AND sale_start <= NOW();
UPDATE show_session se SET se.sale_status = 3
WHERE se.sale_status = 2
  AND EXISTS (SELECT 1 FROM ticket_tier t WHERE t.session_id=se.session_id)  -- 须有票档
  AND NOT EXISTS (SELECT 1 FROM ticket_tier t
                  WHERE t.session_id=se.session_id AND t.total_seats-t.sold_seats > 0);

-- 预期：@se_a 状态=2(售票中，无票档不误判售罄)，@se_b 状态=3(售罄)
SELECT session_id, sale_status,
       ELT(sale_status,'预售中','售票中','售罄') AS status_text
FROM show_session WHERE session_id IN (@se_a, @se_b);

-- 清理测试场次（票档随场次级联删除）
DELETE FROM show_session WHERE session_id IN (@se_a, @se_b);

-- TC-31 销售统计【按天-汇总表，折线图数据】
-- 预期：近 30 天每天一行，含订单数/票数/金额（TC-13 的购票计入今天）
SELECT stat_date, order_count, ticket_count, total_amount
FROM sales_daily
WHERE stat_date BETWEEN DATE_SUB(CURDATE(),INTERVAL 30 DAY) AND CURDATE()
ORDER BY stat_date;

-- TC-32 销售统计【按天-实时明细聚合】
SELECT DATE(pay_time) AS d, COUNT(*) AS order_count,
       SUM(ticket_count) AS tickets, SUM(total_amount) AS amount
FROM ticket_order
WHERE order_status = 2
  AND pay_time BETWEEN DATE_SUB(NOW(),INTERVAL 30 DAY) AND NOW()
GROUP BY DATE(pay_time) ORDER BY d;

-- TC-33 销售统计【按演出类型-饼图数据】
-- 预期：演唱会/话剧歌剧/体育/儿童亲子/展览/音乐会/舞蹈 按金额降序
SELECT cat.category_name,
       SUM(o.ticket_count) AS tickets, SUM(o.total_amount) AS amount
FROM ticket_order o
JOIN show_session se ON se.session_id=o.session_id
JOIN show_item s     ON s.show_id=se.show_id
JOIN category cat    ON cat.category_id=s.category_id
WHERE o.order_status=2
  AND o.pay_time BETWEEN DATE_SUB(NOW(),INTERVAL 60 DAY) AND NOW()
GROUP BY cat.category_id, cat.category_name ORDER BY amount DESC;

-- TC-34 销售统计【按城市-柱状图/地图数据】
SELECT c.city_name,
       SUM(o.ticket_count) AS tickets, SUM(o.total_amount) AS amount
FROM ticket_order o
JOIN show_session se ON se.session_id=o.session_id
JOIN venue v         ON v.venue_id=se.venue_id
JOIN city c          ON c.city_id=v.city_id
WHERE o.order_status=2
  AND o.pay_time BETWEEN DATE_SUB(NOW(),INTERVAL 60 DAY) AND NOW()
GROUP BY c.city_id, c.city_name ORDER BY amount DESC;

-- TC-35 销售统计【热销演出 TOP】
SELECT s.show_name, c.city_name,
       SUM(o.ticket_count) AS tickets, SUM(o.total_amount) AS amount
FROM ticket_order o
JOIN show_session se ON se.session_id=o.session_id
JOIN show_item s     ON s.show_id=se.show_id
JOIN city c          ON c.city_id=s.city_id
WHERE o.order_status=2
  AND o.pay_time BETWEEN DATE_SUB(NOW(),INTERVAL 60 DAY) AND NOW()
GROUP BY s.show_id, s.show_name, c.city_name
ORDER BY tickets DESC LIMIT 10;

-- TC-36 销售统计【单场上座率】
-- 预期：session 1 各档售出率，内场1980 为 100.0%
SELECT s.show_name, se.show_time, v.venue_name,
       t.tier_name, t.total_seats, t.sold_seats,
       ROUND(t.sold_seats/t.total_seats*100,1) AS sell_through_pct
FROM ticket_tier t
JOIN show_session se ON se.session_id=t.session_id
JOIN show_item s     ON s.show_id=se.show_id
JOIN venue v         ON v.venue_id=se.venue_id
WHERE se.session_id = 1 ORDER BY t.price DESC;

-- TC-37 购票请求留痕核对【成功失败全部记录 + 失败原因分布】
-- 预期：能看到 TC-13 成功、TC-14 余票不足、种子数据的限购/未开售等记录
SELECT result,
       CASE result WHEN 1 THEN '成功' ELSE '失败' END AS result_text,
       COUNT(*) AS cnt
FROM purchase_request
WHERE request_time BETWEEN DATE_SUB(NOW(),INTERVAL 30 DAY) AND NOW()
GROUP BY result;

SELECT fail_reason, COUNT(*) AS cnt
FROM purchase_request
WHERE result = 0
  AND request_time BETWEEN DATE_SUB(NOW(),INTERVAL 30 DAY) AND NOW()
GROUP BY fail_reason ORDER BY cnt DESC;

-- ############################################################################
-- 模块十：完整性约束专项
-- ############################################################################

-- TC-38 实体/唯一约束【用户名重复】
-- 预期：[Err] 1062 Duplicate entry 'zhang_san'
INSERT INTO app_user(username,password_hash,phone,status)
VALUES ('zhang_san','x','13700000000',1);

-- TC-39 参照完整性【订单引用不存在的用户】
-- 预期：[Err] 1452 ... foreign key constraint
INSERT INTO ticket_order(order_no,user_id,session_id,tier_id,address_id,
                         ticket_count,total_amount,order_status)
VALUES ('BADREF001', 999999, 1, 3, 1, 1, 580.00, 1);

-- TC-40 CHECK 约束【三种违反】
-- 40a 票价为负：预期 [Err] 3819 Check constraint 'chk_tier_price'
INSERT INTO ticket_tier(session_id,tier_name,price,total_seats)
VALUES (2,'负票价档',-100.00,100);
-- 40b 已售超过总数：预期 [Err] 3819 Check constraint 'chk_tier_sold'
INSERT INTO ticket_tier(session_id,tier_name,price,total_seats,sold_seats)
VALUES (2,'超卖档',100.00,100,101);
-- 40c 订单票数超范围(>6)：预期 [Err] 3819 Check constraint 'chk_order_count'
INSERT INTO ticket_order(order_no,user_id,session_id,tier_id,address_id,
                         ticket_count,total_amount,order_status)
VALUES ('BADCNT001',1,2,5,1,7,4060.00,1);

-- TC-41 唯一约束【同场次票档名重复】
-- 预期：[Err] 1062 Duplicate entry '1-看台 980'（session_id+tier_name 唯一）
INSERT INTO ticket_tier(session_id,tier_name,price,total_seats)
VALUES (1,'看台 980',980.00,100);

-- ############################################################################
-- 模块十一：大数据量（可选，耗时约半分钟~2 分钟）
-- ############################################################################

-- TC-42 批量生成 10 万用户并验证查询性能
/*  -- 取消本块注释后执行
SET SESSION cte_max_recursion_depth = 100000;
INSERT INTO app_user(username,password_hash,phone,email,status)
WITH RECURSIVE seq(k) AS (
  SELECT 1 UNION ALL SELECT k+1 FROM seq WHERE k < 100000
)
SELECT CONCAT('bulk_user',LPAD(k,6,'0')),
       '$2b$10$0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ',
       CONCAT('139',LPAD(k,8,'0')),
       CONCAT('bulk',k,'@example.com'), 1
FROM seq;

-- 42a 总数核对：预期 100005（5 个测试用户 + 10 万）
SELECT COUNT(*) AS total_users FROM app_user;

-- 42b 10 万数据中按用户名精确查找（命中 uk_user_username 索引，毫秒级）
SELECT user_id, username, phone FROM app_user WHERE username = 'bulk_user099999';
EXPLAIN SELECT user_id, username FROM app_user WHERE username = 'bulk_user099999';
-- 预期 EXPLAIN 的 type=const、key=uk_user_username、rows=1

-- 42c 测试后清理（可选）：
-- DELETE FROM app_user WHERE username LIKE 'bulk_%';
*/

-- ############################################################################
-- 模块十二：并发购票模拟（进阶，可选；需要两个查询窗口配合）
-- ############################################################################
-- 背景：tier 24（CBA 一等680）total=2000，初始 sold=1500，余票 500。
-- 【查询窗口 A】执行（不提交，持有行锁）：
--   START TRANSACTION;
--   UPDATE ticket_tier SET sold_seats = sold_seats + 400
--   WHERE tier_id = 24 AND total_seats - sold_seats >= 400;
--   -- 暂不 COMMIT
-- 【查询窗口 B】执行：
--   START TRANSACTION;
--   UPDATE ticket_tier SET sold_seats = sold_seats + 400
--   WHERE tier_id = 24 AND total_seats - sold_seats >= 400;
--   -- 预期：B 被阻塞（行锁等待），直到 A 提交
-- 【窗口 A】执行 COMMIT;  （此时 sold=1900，余票 100）
-- 【窗口 B】预期：等待结束后 ROW_COUNT()=0（400 > 余票100，扣票失败，不超卖）
-- 【窗口 B】执行 ROLLBACK;
-- 验证与复位：
--   SELECT tier_id,total_seats,sold_seats FROM ticket_tier WHERE tier_id=24; -- 1900
--   UPDATE ticket_tier SET sold_seats=1500 WHERE tier_id=24;  -- 复位测试数据
