const pptxgen = require('../.pptx-tools/node_modules/pptxgenjs');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'Codex';
pptx.subject = '演出门票销售系统数据库概念模型与逻辑模型';
pptx.title = '演出门票销售系统数据库模型';
pptx.company = '演出门票销售系统';
pptx.lang = 'zh-CN';

const S = pptx.ShapeType;
const C = {
  ink: '19324A', muted: '63758A', blue: '5C9BD5', blueDark: '2F75B5',
  blueSoft: 'EAF3FB', gold: 'D49B26', goldSoft: 'FFF4D8', line: '6F8DA7',
  white: 'FFFFFF', paper: 'F7FAFC', border: 'D7E3ED', profile: '4B78A8',
  show: '398A70', order: 'C27B2B', log: '8A5AA8', derived: 'A05A5A'
};
const FONT = 'Microsoft YaHei';
const W = 13.333;

function text(slide, value, x, y, w, h, opts = {}) {
  slide.addText(value, {
    x, y, w, h, margin: 0, fontFace: FONT, fontSize: 12, color: C.ink,
    breakLine: false, fit: 'shrink', valign: 'mid', ...opts
  });
}

function title(slide, heading, subtitle, kind = '') {
  slide.background = { color: C.paper };
  text(slide, heading, 0.45, 0.25, 12.4, 0.42, { fontSize: 24, bold: true, color: C.ink });
  if (subtitle) text(slide, subtitle, 0.45, 0.70, 12.4, 0.24, { fontSize: 10.5, color: C.muted });
  if (kind) text(slide, kind, 11.0, 0.31, 1.85, 0.25, { fontSize: 10, color: C.blueDark, align: 'right' });
}

function canvas(rawH, maxH = 5.5) {
  const maxW = 12.4;
  const scale = Math.min(maxW / 1040, maxH / rawH);
  return { left: (W - 1040 * scale) / 2, top: 1.04, scale, rawH };
}
function P(cv, x, y) { return { x: cv.left + x * cv.scale, y: cv.top + y * cv.scale }; }
function R(cv, x, y, w, h) { const p = P(cv, x, y); return { x: p.x, y: p.y, w: w * cv.scale, h: h * cv.scale }; }

function lineSeg(slide, cv, a, b, color = C.line, dash = 'solid', width = 1.15) {
  const p1 = P(cv, a[0], a[1]), p2 = P(cv, b[0], b[1]);
  slide.addShape(S.line, {
    x: Math.min(p1.x, p2.x), y: Math.min(p1.y, p2.y),
    w: Math.max(Math.abs(p2.x - p1.x), 0.001), h: Math.max(Math.abs(p2.y - p1.y), 0.001),
    line: { color, width, dashType: dash }
  });
}
function polyline(slide, cv, points, color = C.line, dash = 'solid', width = 1.15) {
  for (let i = 1; i < points.length; i++) lineSeg(slide, cv, points[i - 1], points[i], color, dash, width);
}
function endpoint(slide, cv, point, color) {
  const p = P(cv, point[0], point[1]);
  slide.addShape(S.ellipse, { x: p.x - 0.035, y: p.y - 0.035, w: 0.07, h: 0.07, fill: { color: C.white }, line: { color, width: 1.1 } });
}

function entity(slide, cv, x, y, w, h, value) {
  const r = R(cv, x, y, w, h);
  slide.addShape(S.rect, { ...r, fill: { color: C.blue }, line: { color: C.blueDark, width: 1 } });
  text(slide, value, r.x, r.y, r.w, r.h, { fontSize: 13, bold: true, color: C.white, align: 'center' });
  return { x, y, w, h };
}
function attr(slide, cv, x, y, w, h, value) {
  const r = R(cv, x, y, w, h);
  slide.addShape(S.ellipse, { ...r, fill: { color: C.blueSoft }, line: { color: '76A7D1', width: 1 } });
  text(slide, value, r.x + 0.02, r.y, r.w - 0.04, r.h, { fontSize: 9.5, align: 'center' });
  return { x, y, w, h };
}
function relationship(slide, cv, x, y, w, h, value) {
  const p = P(cv, x, y), ww = w * cv.scale, hh = h * cv.scale;
  slide.addShape(S.diamond, { x: p.x, y: p.y - hh / 2, w: ww, h: hh, fill: { color: C.goldSoft }, line: { color: C.gold, width: 1 } });
  text(slide, value, p.x, p.y - hh / 2, ww, hh, { fontSize: 9.5, color: '6B4B05', align: 'center' });
}
function cardinality(slide, cv, x, y, value) {
  const p = P(cv, x, y);
  text(slide, value, p.x, p.y - 0.08, 0.22, 0.16, { fontSize: 8.5, bold: true, color: C.ink, align: 'center' });
}
function conceptLink(slide, cv, points, label, ca = '1', cb = 'N') {
  polyline(slide, cv, points, C.line, 'solid', 1.05);
  cardinality(slide, cv, points[0][0] + 4, points[0][1] - 1, ca);
  const q = points[points.length - 1];
  cardinality(slide, cv, q[0] - 16, q[1] - 1, cb);
  const mid = points[Math.floor(points.length / 2)];
  relationship(slide, cv, mid[0] - 46, mid[1] - 19, 92, 38, label);
}
function attrLink(slide, cv, e, a, side = 'top') {
  const p = side === 'top'
    ? [[e.x + e.w / 2, e.y], [a.x + a.w / 2, a.y + a.h]]
    : side === 'bottom'
      ? [[e.x + e.w / 2, e.y + e.h], [a.x + a.w / 2, a.y]]
      : side === 'left'
        ? [[e.x, e.y + e.h / 2], [a.x + a.w, a.y + a.h / 2]]
        : [[e.x + e.w, e.y + e.h / 2], [a.x, a.y + a.h / 2]];
  polyline(slide, cv, p, C.line, 'solid', 1.0);
}

function addConcept1(slide) {
  const cv = canvas(470, 5.55);
  title(slide, '1. 演出基础信息：概念模型', '城市、场馆、类型、管理员、演出、场次和票档。', '概念模型');
  const city = entity(slide, cv, 70, 190, 140, 54, '城市');
  const venue = entity(slide, cv, 340, 190, 140, 54, '场馆');
  const cat = entity(slide, cv, 70, 350, 140, 54, '演出类型');
  const show = entity(slide, cv, 340, 350, 140, 54, '演出');
  const admin = entity(slide, cv, 610, 350, 140, 54, '管理员');
  const ses = entity(slide, cv, 610, 190, 140, 54, '演出场次');
  const tier = entity(slide, cv, 880, 190, 140, 54, '票档');
  conceptLink(slide, cv, [[210,247],[294,247],[294,217],[340,217]], '位于');
  conceptLink(slide, cv, [[140,274],[140,315],[300,315],[300,377],[340,377]], '举办');
  conceptLink(slide, cv, [[210,377],[294,377],[294,377],[340,377]], '分类');
  conceptLink(slide, cv, [[480,377],[550,377],[550,217],[610,217]], '安排');
  conceptLink(slide, cv, [[750,217],[815,217],[815,217],[880,217]], '设置');
  conceptLink(slide, cv, [[610,377],[570,377],[570,450],[500,450],[500,404],[480,404]], '创建');
  attrLink(slide, cv, city, attr(slide, cv, 82,105,116,34,'城市ID'));
  attrLink(slide, cv, venue, attr(slide, cv, 352,105,116,34,'场馆名称'));
  attrLink(slide, cv, cat, attr(slide, cv, 82,265,116,34,'类型名称'));
  attrLink(slide, cv, show, attr(slide, cv, 352,425,116,34,'演出名称'), 'bottom');
  attrLink(slide, cv, ses, attr(slide, cv, 622,105,116,34,'演出日期'));
  attrLink(slide, cv, tier, attr(slide, cv, 892,105,116,34,'价格/票数'));
  attrLink(slide, cv, admin, attr(slide, cv, 622,425,116,34,'管理员ID'), 'bottom');
}
function addConcept2(slide) {
  const cv = canvas(360, 5.55);
  title(slide, '2. 用户资料：概念模型', '用户保存收货信息和常用购票人。', '概念模型');
  const u = entity(slide, cv,130,155,150,54,'用户');
  const ad = entity(slide, cv,510,90,160,54,'收货信息');
  const at = entity(slide, cv,510,245,160,54,'常用购票人');
  conceptLink(slide, cv, [[280,182],[395,182],[395,117],[510,117]], '保存');
  conceptLink(slide, cv, [[280,182],[395,182],[395,272],[510,272]], '维护');
  attrLink(slide, cv, u, attr(slide, cv,147,70,116,34,'用户名'));
  attrLink(slide, cv, ad, attr(slide, cv,532,10,116,34,'收货地址'));
  attrLink(slide, cv, at, attr(slide, cv,532,300,116,34,'姓名/证件号'), 'bottom');
}
function addConcept3(slide) {
  const cv = canvas(520, 5.5);
  title(slide, '3. 订单与购票：概念模型', '订单对应场次、选择票档、使用地址，并包含订单明细。', '概念模型');
  const u=entity(slide,cv,60,235,140,54,'用户'), ad=entity(slide,cv,60,395,140,54,'收货信息');
  const ses=entity(slide,cv,330,75,140,54,'演出场次'), tier=entity(slide,cv,570,75,140,54,'票档');
  const ord=entity(slide,cv,330,235,140,54,'订单'), item=entity(slide,cv,800,235,160,54,'订单明细');
  const att=entity(slide,cv,570,395,140,54,'常用购票人');
  conceptLink(slide,cv,[[200,262],[264,262],[264,262],[330,262]],'提交');
  conceptLink(slide,cv,[[200,422],[230,422],[230,320],[330,320],[330,289]],'使用地址');
  conceptLink(slide,cv,[[400,129],[400,180],[400,235]],'对应场次');
  conceptLink(slide,cv,[[640,129],[640,150],[760,150],[760,205],[450,205],[450,235]],'选择票档');
  conceptLink(slide,cv,[[470,262],[635,262],[635,262],[800,262]],'包含','1','1..N');
  conceptLink(slide,cv,[[710,422],[760,422],[760,330],[800,330],[800,289]],'持有');
  attrLink(slide,cv,ord,attr(slide,cv,342,315,116,34,'订单金额'),'bottom');
  attrLink(slide,cv,item,attr(slide,cv,822,315,116,34,'购票人'),'bottom');
}
function addConcept4(slide) {
  const cv = canvas(360, 5.55);
  title(slide, '4. 请求与销售统计：概念模型', '购票请求记录成功或失败；支付成功订单派生销售统计。', '概念模型');
  const u=entity(slide,cv,50,145,140,54,'用户'), ses=entity(slide,cv,300,55,140,54,'演出场次');
  const tier=entity(slide,cv,520,55,140,54,'票档'), req=entity(slide,cv,300,145,160,54,'购票请求');
  const ord=entity(slide,cv,700,145,140,54,'订单'), daily=entity(slide,cv,700,275,160,54,'销售统计');
  conceptLink(slide,cv,[[190,172],[245,172],[245,172],[300,172]],'记录');
  conceptLink(slide,cv,[[370,109],[370,125],[370,125],[380,145]],'针对');
  conceptLink(slide,cv,[[590,109],[590,125],[510,125],[510,145]],'请求票档');
  conceptLink(slide,cv,[[840,172],[920,172],[920,240],[860,240],[860,302]],'支付成功后汇总','1','N');
  attrLink(slide,cv,req,attr(slide,cv,322,235,116,34,'处理结果'),'bottom');
  attrLink(slide,cv,daily,attr(slide,cv,722,325,160,34,'销售数量/金额'),'bottom');
}

const tables = {
  user:{name:'APP_USER 用户',fields:[['PK','user_id'],['','username'],['','password'],['','phone']]},
  city:{name:'CITY 城市',fields:[['PK','city_id'],['','city_name']]},
  cat:{name:'CATEGORY 演出类型',fields:[['PK','category_id'],['','category_name']]},
  admin:{name:'ADMIN 管理员',fields:[['PK','admin_id'],['','username'],['','password']]},
  address:{name:'SHIPPING_ADDRESS 收货信息',fields:[['PK','address_id'],['FK','user_id'],['','receiver_name'],['','phone'],['','address_detail']]},
  venue:{name:'VENUE 场馆',fields:[['PK','venue_id'],['FK','city_id'],['','venue_name'],['','address']]},
  show:{name:'SHOW 演出',fields:[['PK','show_id'],['FK','category_id'],['FK','city_id'],['FK','admin_id'],['','show_name'],['','description']]},
  session:{name:'SHOW_SESSION 演出场次',fields:[['PK','session_id'],['FK','show_id'],['FK','venue_id'],['','show_time'],['','sale_status']]},
  tier:{name:'TICKET_TIER 票档',fields:[['PK','tier_id'],['FK','session_id'],['','tier_name'],['','price'],['','total_seats']]},
  attendee:{name:'ATTENDEE 常用购票人',fields:[['PK','attendee_id'],['FK','user_id'],['','attendee_name'],['','id_type'],['','id_no']]},
  order:{name:'TICKET_ORDER 订单',fields:[['PK','order_id'],['FK','user_id'],['FK','session_id'],['FK','tier_id'],['FK','address_id'],['','ticket_count'],['','total_amount'],['','order_status']]},
  item:{name:'ORDER_ITEM 订单明细',fields:[['PK','item_id'],['FK','order_id'],['FK','attendee_id'],['','unit_price']]},
  request:{name:'PURCHASE_REQUEST 购票请求',fields:[['PK','request_id'],['','user_id'],['','session_id'],['','tier_id'],['','ticket_count'],['','result']]},
  daily:{name:'SALES_DAILY 销售统计',fields:[['PK','stat_date'],['','order_count'],['','ticket_count'],['','total_amount']]}
};

function table(slide, cv, x, y, t) {
  const h = 30 + t.fields.length * 23 + 8;
  const r = R(cv, x, y, 210, h);
  slide.addShape(S.rect, { ...r, fill: { color: C.white }, line: { color: '76A7D1', width: 1 } });
  const head = R(cv, x, y, 210, 30);
  slide.addShape(S.rect, { ...head, fill: { color: C.blue }, line: { color: C.blue, width: 0.5 } });
  text(slide, t.name, head.x + 0.06, head.y, head.w - 0.12, head.h, { fontSize: 8.5, bold: true, color: C.white });
  const rows = {};
  t.fields.forEach((f, i) => {
    const yy = y + 51 + i * 23;
    rows[f[1]] = yy;
    const row = R(cv, x, yy - 12, 210, 23);
    slide.addShape(S.line, { x: row.x, y: row.y + row.h, w: row.w, h: 0, line: { color: 'D7E3ED', width: 0.45 } });
    text(slide, f[0], row.x + 0.06, row.y, 0.28, row.h, { fontSize: 7.2, bold: f[0] !== '', color: f[0] === 'PK' ? 'A76800' : f[0] === 'FK' ? C.blueDark : C.muted });
    text(slide, f[1], row.x + 0.42, row.y, row.w - 0.48, row.h, { fontSize: 7.8 });
  });
  return { x, y, w: 210, h, rows };
}
function edge(slide, cv, pts, color, dash = 'solid') {
  polyline(slide, cv, pts, color, dash, 1.15);
  endpoint(slide, cv, pts[0], color);
  endpoint(slide, cv, pts[pts.length - 1], color);
}

function addLogical1(slide) {
  const cv = canvas(500, 5.25);
  title(slide, '1. 演出基础表：逻辑模型', 'PK/FK 字段保留在可编辑表格中；连线端点对齐到字段行。', '逻辑模型');
  const m={city:table(slide,cv,30,40,tables.city),cat:table(slide,cv,280,40,tables.cat),admin:table(slide,cv,530,40,tables.admin),venue:table(slide,cv,30,260,tables.venue),show:table(slide,cv,280,260,tables.show),ses:table(slide,cv,530,260,tables.session),tier:table(slide,cv,780,260,tables.tier)};
  edge(slide,cv,[[30,334],[14,334],[14,91],[30,91]],C.show);
  edge(slide,cv,[[280,334],[264,334],[264,91],[280,91]],C.show);
  edge(slide,cv,[[280,357],[252,357],[252,145],[240,145],[240,91]],C.show);
  edge(slide,cv,[[490,380],[510,380],[510,145],[530,145],[530,91]],C.show);
  edge(slide,cv,[[530,334],[512,334],[512,311],[490,311]],C.show);
  edge(slide,cv,[[740,357],[760,357],[760,470],[240,470],[240,311]],C.show);
  edge(slide,cv,[[780,334],[760,334],[760,311],[740,311]],C.show);
  Object.values(m).forEach(() => {});
  slide.addNotes('主外键映射：VENUE.city_id → CITY.city_id；SHOW.category_id → CATEGORY.category_id；SHOW.city_id → CITY.city_id；SHOW.admin_id → ADMIN.admin_id；SHOW_SESSION.show_id → SHOW.show_id；SHOW_SESSION.venue_id → VENUE.venue_id；TICKET_TIER.session_id → SHOW_SESSION.session_id。');
}
function addLogical2(slide) {
  const cv = canvas(360, 5.35);
  title(slide, '2. 用户资料表：逻辑模型', '收货信息和常用购票人均通过 user_id 关联用户。', '逻辑模型');
  const m={user:table(slide,cv,80,80,tables.user),ad:table(slide,cv,420,45,tables.address),at:table(slide,cv,420,220,tables.attendee)};
  edge(slide,cv,[[420,119],[350,119],[350,131],[290,131]],C.profile);
  edge(slide,cv,[[420,294],[330,294],[330,154],[290,154]],C.profile);
  slide.addNotes('主外键映射：SHIPPING_ADDRESS.user_id → APP_USER.user_id；ATTENDEE.user_id → APP_USER.user_id。');
}
function addLogical3(slide) {
  const cv = canvas(540, 5.35);
  title(slide, '3. 订单交易表：逻辑模型', '订单、订单明细、场次、票档、地址和购票人的字段级关系。', '逻辑模型');
  const m={user:table(slide,cv,30,50,tables.user),ad:table(slide,cv,30,300,tables.address),ses:table(slide,cv,300,50,tables.session),tier:table(slide,cv,570,50,tables.tier),ord:table(slide,cv,300,300,tables.order),item:table(slide,cv,800,300,tables.item),at:table(slide,cv,560,360,tables.attendee)};
  edge(slide,cv,[[300,374],[270,374],[270,124],[240,124]],C.order);
  edge(slide,cv,[[300,397],[280,397],[280,101],[300,101]],C.order);
  edge(slide,cv,[[510,420],[530,420],[530,101],[570,101]],C.order);
  edge(slide,cv,[[300,443],[270,443],[270,351],[240,351]],C.order);
  edge(slide,cv,[[800,374],[790,374],[790,330],[510,330],[510,351]],C.order);
  edge(slide,cv,[[800,397],[785,397],[785,411],[770,411]],C.order);
  slide.addNotes('主外键映射：TICKET_ORDER.user_id → APP_USER.user_id；TICKET_ORDER.session_id → SHOW_SESSION.session_id；TICKET_ORDER.tier_id → TICKET_TIER.tier_id；TICKET_ORDER.address_id → SHIPPING_ADDRESS.address_id；ORDER_ITEM.order_id → TICKET_ORDER.order_id；ORDER_ITEM.attendee_id → ATTENDEE.attendee_id。组合一致性约束：TICKET_ORDER(session_id, tier_id) 与 TICKET_TIER(session_id, tier_id) 成对对应。');
}
function addLogical4(slide) {
  const cv = canvas(360, 5.35);
  title(slide, '4. 请求与统计表：逻辑模型', '请求上下文与销售统计的来源关系。', '逻辑模型');
  const m={user:table(slide,cv,40,55,tables.user),ses:table(slide,cv,300,55,tables.session),tier:table(slide,cv,560,55,tables.tier),req:table(slide,cv,300,230,tables.request),ord:table(slide,cv,560,230,tables.order),daily:table(slide,cv,820,230,tables.daily)};
  edge(slide,cv,[[300,304],[275,304],[275,106],[250,106]],C.log,'dash');
  edge(slide,cv,[[300,327],[285,327],[285,106],[300,106]],C.log,'dash');
  edge(slide,cv,[[510,350],[530,350],[530,106],[560,106]],C.log,'dash');
  edge(slide,cv,[[770,230],[795,230],[820,230]],C.derived,'dash');
  slide.addNotes('说明：PURCHASE_REQUEST.user_id、session_id、tier_id 是请求上下文记录，当前基础 DDL 未声明为物理外键；SALES_DAILY 是由订单汇总得到的派生表。');
}

function addMappingSlide(slide) {
  title(slide, '主外键映射总表', '可作为提交或答辩时的字段关系对照页。', '字段参考');
  const sections = [
    ['演出基础表', 'VENUE.city_id → CITY.city_id\nSHOW.category_id → CATEGORY.category_id\nSHOW.city_id → CITY.city_id\nSHOW.admin_id → ADMIN.admin_id\nSHOW_SESSION.show_id → SHOW.show_id\nSHOW_SESSION.venue_id → VENUE.venue_id\nTICKET_TIER.session_id → SHOW_SESSION.session_id'],
    ['用户资料表', 'SHIPPING_ADDRESS.user_id → APP_USER.user_id\nATTENDEE.user_id → APP_USER.user_id'],
    ['订单交易表', 'TICKET_ORDER.user_id → APP_USER.user_id\nTICKET_ORDER.session_id → SHOW_SESSION.session_id\nTICKET_ORDER.tier_id → TICKET_TIER.tier_id\nTICKET_ORDER.address_id → SHIPPING_ADDRESS.address_id\nORDER_ITEM.order_id → TICKET_ORDER.order_id\nORDER_ITEM.attendee_id → ATTENDEE.attendee_id'],
    ['请求与统计表', 'PURCHASE_REQUEST 的 user_id、session_id、tier_id 为上下文字段，当前基础 DDL 未声明为外键。\nSALES_DAILY 为订单汇总得到的派生表。']
  ];
  const boxes = [[0.55,1.2,6.0,2.2],[6.78,1.2,6.0,2.2],[0.55,3.75,6.0,2.35],[6.78,3.75,6.0,2.35]];
  sections.forEach((sec, i) => {
    const [x,y,w,h] = boxes[i];
    slide.addShape(S.roundRect, { x, y, w, h, rectRadius: 0.08, fill: { color: C.white }, line: { color: C.border, width: 1 } });
    text(slide, sec[0], x+0.18, y+0.16, w-0.36, 0.28, { fontSize: 15, bold: true, color: C.blueDark });
    text(slide, sec[1], x+0.18, y+0.55, w-0.36, h-0.68, { fontSize: 10.2, breakLine: true, valign: 'top', fit: 'shrink' });
  });
}

const slides = [
  { kind: 'title' },
  { fn: addConcept1 }, { fn: addConcept2 }, { fn: addConcept3 }, { fn: addConcept4 },
  { fn: addLogical1 }, { fn: addLogical2 }, { fn: addLogical3 }, { fn: addLogical4 },
  { fn: addMappingSlide }
];

slides.forEach((entry, index) => {
  const slide = pptx.addSlide();
  if (entry.kind === 'title') {
    slide.background = { color: C.ink };
    text(slide, '演出门票销售系统', 0.75, 1.45, 11.8, 0.65, { fontSize: 32, bold: true, color: C.white, align: 'center' });
    text(slide, '数据库概念模型与逻辑模型', 0.75, 2.25, 11.8, 0.52, { fontSize: 24, color: 'C9DDF0', align: 'center' });
    slide.addShape(S.roundRect, { x: 3.15, y: 3.2, w: 7.05, h: 1.15, rectRadius: 0.08, fill: { color: '244866' }, line: { color: '5C9BD5', width: 1.1 } });
    text(slide, '4 张概念模型图  ·  4 张逻辑模型图  ·  主外键映射总表', 3.35, 3.48, 6.65, 0.45, { fontSize: 15, color: C.white, align: 'center' });
    text(slide, '所有图形均为可编辑的 PowerPoint 形状', 0.75, 6.65, 11.8, 0.24, { fontSize: 10.5, color: 'A9C2D7', align: 'center' });
  } else {
    entry.fn(slide);
  }
  slide.addNotes(index === 0 ? '演出门票销售系统数据库模型。' : '本页图形可直接在 PowerPoint 中编辑。');
});

pptx.writeFile({ fileName: 'docs/database_models.pptx' });
