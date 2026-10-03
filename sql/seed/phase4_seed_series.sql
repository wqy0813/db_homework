-- 第 4 期：为 8 个种子演出创建巡演/IP（series）并关联
USE ticket_sales;

-- 1) 建 8 个巡演/IP（主演照片用本地 static/img 真实图，按人区分）
INSERT INTO show_series (series_id, series_name, category_id, main_artist, poster_url, description) VALUES
  (1, '周杰伦《嘉年华》世界巡回演唱会', 1, '周杰伦', '/static/img/concert1.jpg',
     '周杰伦《嘉年华》世界巡回演唱会，经典曲目全新编排，豪华舞美呈现。'),
  (2, '张学友《60+》巡回演唱会',        1, '张学友', '/static/img/concert2.jpg',
     '歌神张学友 60+ 巡演，数十首经典金曲，现场交响乐团编制。'),
  (3, '话剧《雷雨》',                   2, '北京人艺', '/static/img/theater1.jpg',
     '曹禺经典话剧《雷雨》，北京人民艺术剧院班底演出。'),
  (4, 'CBA 常规赛',                     3, 'CBA联赛', '/static/img/basket1.jpg',
     'CBA 常规赛焦点对决，强强对话一票难求。'),
  (6, '莫奈《光影》沉浸式艺术展',       5, '莫奈', '/static/img/museum1.jpg',
     '莫奈《光影》沉浸式数字艺术展，重现睡莲与日出印象。'),
  (7, '郎朗钢琴独奏音乐会',             6, '郎朗', '/static/img/piano1.jpg',
     '国际钢琴大师郎朗独奏音乐会。'),
  (8, '舞剧《只此青绿》',               7, '中国东方演艺集团', '/static/img/dance1.jpg',
     '现象级舞剧《只此青绿》，以《千里江山图》为灵感。')
ON DUPLICATE KEY UPDATE
  series_name = VALUES(series_name), category_id = VALUES(category_id),
  main_artist = VALUES(main_artist), poster_url = VALUES(poster_url),
  description = VALUES(description);

-- 2) 关联 7 个种子演出到对应巡演（儿童剧已删除）
UPDATE show_item SET series_id = 1 WHERE show_id = 1;
UPDATE show_item SET series_id = 2 WHERE show_id = 2;
UPDATE show_item SET series_id = 3 WHERE show_id = 3;
UPDATE show_item SET series_id = 4 WHERE show_id = 4;
UPDATE show_item SET series_id = 6 WHERE show_id = 6;
UPDATE show_item SET series_id = 7 WHERE show_id = 7;
UPDATE show_item SET series_id = 8 WHERE show_id = 8;
