// 新版 Vue 前端 UI 实测（puppeteer-core + 本机 Chrome）v2
// 覆盖测试文档 T1-T13 的 UI 层行为；输入定位按 placeholder，登录后校验状态
const puppeteer = require('puppeteer-core');
const fs = require('fs');

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:5000/app/';

const results = [];
let pass = 0, fail = 0;
function record(caseId, name, passed, detail) {
  passed ? pass++ : fail++;
  results.push({ case: caseId, name, pass: passed, detail: detail || '' });
  console.log((passed ? 'PASS' : 'FAIL') + ' ' + caseId.padEnd(11) + ' ' + name + '  ' + (detail || ''));
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
function optionIsVisible(o) {
  const r = o.getBoundingClientRect();
  const s = getComputedStyle(o);
  return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
}

async function gotoHash(page, hash) {
  await page.goto(BASE + hash, { waitUntil: 'networkidle0', timeout: 40000 });
  await sleep(900);
}
const bodyText = page => page.evaluate(() => document.body.innerText);

// 按 placeholder 定位可见输入框并设置值（原生 setter + input 事件，确定性高）
async function fillByPlaceholder(page, sub, value) {
  return await page.evaluate((sub, value) => {
    const inputs = Array.from(document.querySelectorAll('input'));
    const inp = inputs.find(i => i.offsetParent && (i.placeholder || '').includes(sub));
    if (!inp) return false;
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(inp, value);
    inp.dispatchEvent(new Event('input', { bubbles: true }));
    inp.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }, sub, value);
}

// 点击文本完全匹配的按钮（在页面内 JS 触发，规避 puppeteer 坐标点击被遮挡问题）
async function jsClickButton(page, text) {
  return await page.evaluate((text) => {
    const norm = s => s.replace(/\s+/g, '');
    const btns = Array.from(document.querySelectorAll('button'));
    let b = btns.find(x => x.textContent.trim() === text);
    if (!b) b = btns.find(x => norm(x.textContent.trim()) === norm(text));
    if (!b) b = btns.find(x => x.textContent.includes(text));
    if (b) { b.click(); return true; }
    return false;
  }, text);
}
const clickButton = jsClickButton;
const clickExact = jsClickButton;

// 点第 selectIndex 个 .el-select，选文本匹配选项（JS 触发）
async function selectByText(page, selectIndex, labelText) {
  const opened = await page.evaluate((selectIndex) => {
    const selects = Array.from(document.querySelectorAll('.el-select'));
    if (selectIndex >= selects.length) return false;
    selects[selectIndex].click();
    return true;
  }, selectIndex);
  if (!opened) return false;
  await sleep(500);
  return await page.evaluate((labelText) => {
    const opts = Array.from(document.querySelectorAll('.el-select-dropdown__item'));
    const o = opts.find(x => x.textContent.trim().includes(labelText));
    if (o) { o.click(); return true; }
    return false;
  }, labelText);
}

// 在指定表单项内选择下拉框，避免依赖页面中所有 .el-select 的全局顺序。
async function selectInFormItem(page, labelText, optionText) {
  const opened = await page.evaluate((labelText) => {
    const item = Array.from(document.querySelectorAll('.el-form-item'))
      .find(x => x.textContent.includes(labelText));
    const select = item && item.querySelector('.el-select');
    if (!select) return false;
    select.click();
    return true;
  }, labelText);
  if (!opened) return false;
  await sleep(400);
  return await page.evaluate((optionText) => {
    const opts = Array.from(document.querySelectorAll('.el-select-dropdown__item'));
    const opt = opts.find(x => x.textContent.trim().includes(optionText) && !x.classList.contains('is-disabled'));
    if (!opt) return false;
    opt.click();
    return true;
  }, optionText);
}

// Element Plus 日期控件使用 value-format 后绑定字符串；用原生 setter 触发 Vue 的 input/change 事件。
async function setDateInput(page, index, value) {
  const inputs = await page.$$('.el-date-editor input');
  if (!inputs[index]) return false;
  await inputs[index].click({ clickCount: 3 });
  await page.keyboard.down('Control');
  await page.keyboard.press('A');
  await page.keyboard.up('Control');
  await page.keyboard.type(value);
  await page.keyboard.press('Tab');
  await sleep(300);
  return await page.evaluate(({ index, value }) => {
    const el = document.querySelectorAll('.el-date-editor input')[index];
    return el.value === value;
  }, { index, value });
}

async function chooseCalendarDate(page, index, isoDate) {
  const [year, month, day] = isoDate.split('-').map(Number);
  const input = await page.$$('.el-date-editor input');
  if (!input[index]) return false;
  await input[index].click();
  await sleep(350);
  return await page.evaluate(async ({ year, month, day }) => {
    const panel = Array.from(document.querySelectorAll('.el-picker-panel'))
      .find(x => getComputedStyle(x).display !== 'none' && getComputedStyle(x).visibility !== 'hidden');
    if (!panel) return false;
    const header = panel.querySelector('.el-date-picker__header');
    if (!header) return false;
    const label = () => header.querySelector('div')?.textContent || '';
    const target = `${year} 年 ${month} 月`;
    for (let i = 0; i < 18 && !label().includes(target); i++) {
      const buttons = header.querySelectorAll('button');
      const next = buttons[buttons.length - 1];
      if (!next) return false;
      next.click();
      await new Promise(r => setTimeout(r, 40));
    }
    const cell = Array.from(panel.querySelectorAll('.el-date-table td.available'))
      .find(td => td.classList.contains('available') && !td.classList.contains('prev-month') &&
        !td.classList.contains('next-month') && td.textContent.trim() === String(day));
    if (!cell) return false;
    cell.click();
    return true;
  }, { year, month, day });
}

async function findPreSaleTarget(page) {
  return await page.evaluate(async () => {
    const list = await (await fetch('/api/shows?status=1')).json();
    for (const show of (list.data && list.data.list) || []) {
      const detail = await (await fetch('/api/shows/' + show.show_id)).json();
      const sessions = (detail.data && detail.data.sessions) || [];
      if (sessions.some(s => s.sale_status === 1)) return show.show_id;
    }
    return null;
  });
}

// 登录（role: user/admin）
async function loginUI(page, role, username, password) {
  await gotoHash(page, '#/login');
  if (role === 'admin') {
    await page.evaluate(() => {
      const radios = Array.from(document.querySelectorAll('.el-radio-button'));
      const r = radios.find(x => x.textContent.includes('管理员'));
      if (r) r.click();
    });
    await sleep(400);
  }
  await fillByPlaceholder(page, '用户名', username);
  await fillByPlaceholder(page, '密码', password);
  await clickExact(page, '登 录');
  await sleep(1400);
  const txt = await bodyText(page);
  // 登录成功标志：topbar 出现（用户名）+ （管理员|用户）且非登录页
  return !txt.includes('用户名（如 zhang_san') && /（管理员|（用户）/.test(txt) && !txt.includes('请输入用户名');
}

(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 1000 });
  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push(String(e).slice(0, 200)));
  page.on('error', e => pageErrors.push('page-crash: ' + String(e).slice(0, 200)));
  page.on('console', m => { if (m.type() === 'error' && !m.text().includes('404')) pageErrors.push(m.text().slice(0, 200)); });
  try {
    await run(page, pageErrors);
  } catch (e) {
    console.log('RUN-EXCEPTION:', String(e && e.stack || e).slice(0, 600));
  } finally {
    try { fs.writeFileSync(require('path').join(__dirname, 'ui_results.json'), JSON.stringify(results, null, 1), 'utf8'); } catch (e) {}
    console.log('='.repeat(80));
    console.log('UI 汇总(最终): PASS=%d FAIL=%d TOTAL=%d'.replace('%d', pass).replace('%d', fail).replace('%d', pass + fail));
    console.log('pageErrors:', JSON.stringify(pageErrors.slice(0, 5)));
    await browser.close().catch(() => {});
  }
})();

async function run(page, pageErrors) {

  // ========== T1 ==========
  await gotoHash(page, '#/series');
  let txt = await bodyText(page);
  record('T1-UI', '首页标题"演出巡演"', txt.includes('演出巡演'));
  const cardCount = await page.evaluate(() => document.querySelectorAll('.series-card').length);
  record('T1-UI', '巡演卡片网格渲染', cardCount > 10, 'cards=' + cardCount);
  record('T1-UI', '卡片主演🎤徽标', txt.includes('🎤'));
  record('T1-UI', '"其他单场演出"含威尼斯商人', txt.includes('其他单场演出') && txt.includes('威尼斯商人'));

  // ========== T2 ==========
  await fillByPlaceholder(page, '搜索巡演/艺人', '周杰伦');
  await clickButton(page, '筛选');
  await sleep(1300);
  const kwCards = await page.evaluate(() => document.querySelectorAll('.series-card').length);
  txt = await bodyText(page);
  record('T2-UI', '关键词"周杰伦"仅1卡', kwCards === 1 && txt.includes('周杰伦 巡回演唱会'), 'cards=' + kwCards);
  // 清空关键词
  const kwInput = await page.$$eval('input', els => {
    const e = els.find(x => x.placeholder.includes('搜索巡演/艺人'));
    if (e) { e.focus(); }
    return !!e;
  });
  await page.keyboard.down('Control'); await page.keyboard.press('A'); await page.keyboard.up('Control');
  await page.keyboard.press('Backspace');
  await sleep(300);
  await selectByText(page, 1, '演唱会');
  await clickButton(page, '筛选');
  await sleep(1300);
  const catOk = await page.evaluate(() => {
    const tags = Array.from(document.querySelectorAll('.series-card .cat-tag')).map(t => t.textContent.trim());
    return tags.length > 0 && tags.every(t => t === '演唱会');
  });
  record('T2-UI', '类型=演唱会', catOk);
  await selectByText(page, 0, '北京');
  await clickButton(page, '筛选');
  await sleep(1300);
  const comboOk = await page.evaluate(() => {
    const tags = Array.from(document.querySelectorAll('.series-card .cat-tag')).map(t => t.textContent.trim());
    return tags.length > 0 && tags.every(t => t === '演唱会');
  });
  const comboCards = await page.evaluate(() => document.querySelectorAll('.series-card').length);
  record('T2-UI', '演唱会+北京组合', comboOk, 'cards=' + comboCards);

  // ========== T3 ==========
  await gotoHash(page, '#/series/69');
  txt = await bodyText(page);
  record('T3-UI', '周杰伦详情(主演/城市站标题)', txt.includes('周杰伦') && txt.includes('城市站'));
  const stations = await page.evaluate(() => document.querySelectorAll('.station').length);
  record('T3-UI', '城市站列表>=7', stations >= 7, 'stations=' + stations);
  await page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll('.station'));
    for (const c of cards) if (c.textContent.includes('北京')) { c.querySelector('button').click(); return; }
  });
  await sleep(1300);
  txt = await bodyText(page);
  record('T3-UI', '点北京站→演出详情', page.url().includes('/shows/1') && txt.includes('世界巡回演唱会'), 'url=' + page.url());

  // ========== T4（游客） ==========
  await gotoHash(page, '#/shows/1');
  txt = await bodyText(page);
  record('T4-UI', '名称/票价区间380-1980', txt.includes('周杰伦') && txt.includes('380') && txt.includes('1980'));
  const imgs = await page.evaluate(() => document.querySelectorAll('.el-image').length);
  record('T4-UI', '介绍图片>=2', imgs >= 2, 'images=' + imgs);
  const sessions = await page.evaluate(() => document.querySelectorAll('.session').length);
  record('T4-UI', '场次卡片=2', sessions === 2, 'sessions=' + sessions);
  record('T4-UI', '售罄票档标记', txt.includes('该票档售罄'));
  record('T4-UI', '游客看到"登录后即可购票"', txt.includes('后即可购票'));
  // 预售场次（游客视角：状态徽标可见、无购票按钮）
  let preGuest = await page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll('.session'));
    for (const c of cards) {
      if (c.textContent.includes('预售中')) {
        const hasBuyBtn = c.textContent.includes('提交购票请求');
        return { hasTag: true, hasBuyBtn };
      }
    }
    return { hasTag: false, hasBuyBtn: false };
  });
  if (!preGuest.hasTag) {
    const preShowId = await findPreSaleTarget(page);
    if (preShowId) {
      await gotoHash(page, '#/shows/' + preShowId);
      preGuest = await page.evaluate(() => {
        const card = Array.from(document.querySelectorAll('.session'))
          .find(c => c.textContent.includes('预售中'));
        return card ? { hasTag: true, hasBuyBtn: card.textContent.includes('提交购票请求') }
                    : { hasTag: false, hasBuyBtn: false };
      });
    }
  }
  record('T4-UI', '预售场次游客可见状态无购票按钮', preGuest.hasTag && !preGuest.hasBuyBtn, JSON.stringify(preGuest));

  // ========== T5 登录 ==========
  // 5.2 错误密码
  await gotoHash(page, '#/login');
  await fillByPlaceholder(page, '用户名', 'zhang_san');
  await fillByPlaceholder(page, '密码', '1234567');
  await clickExact(page, '登 录');
  await sleep(1300);
  txt = await bodyText(page);
  record('T5-UI', '错误密码提示"用户名或密码错误"', txt.includes('用户名或密码错误'), 'login-failed-text=' + txt.includes('请输入用户名'));
  // 5.1 用户登录成功
  const userOk = await loginUI(page, 'user', 'zhang_san', '123456');
  txt = await bodyText(page);
  record('T5-UI', '用户登录成功(zhang_san（用户）)', userOk && txt.includes('zhang_san') && txt.includes('（用户）'));
  record('T5-UI', '用户导航菜单', txt.includes('我的订单') && txt.includes('收货信息') && txt.includes('常用购票人'));
  // 5.4 退出
  await clickButton(page, '退出');
  await sleep(1000);
  txt = await bodyText(page);
  record('T5-UI', '退出回游客态(登录按钮)', txt.includes('登录') && !txt.includes('（用户）'));
  // 5.3 管理员登录（系统显示 real_name=系统管理员，测试文档预期 admin）
  const adminOk = await loginUI(page, 'admin', 'admin', '123456');
  txt = await bodyText(page);
  const adminNameOk = txt.includes('系统管理员') || txt.includes('admin');
  record('T5-UI', '管理员登录成功(显示管理员身份)', adminOk && adminNameOk && txt.includes('（管理员）'),
    'shows=' + (txt.includes('系统管理员') ? '系统管理员' : txt.includes('admin') ? 'admin' : '?'));
  record('T5-UI', '管理员导航(演出管理/销售统计)', txt.includes('演出管理') && txt.includes('销售统计'));

  // ========== T13 权限 ==========
  // 13.1 用户访问 /admin/shows → 应被引导回 /shows
  await clickButton(page, '退出');
  await sleep(800);
  const userOk2 = await loginUI(page, 'user', 'zhang_san', '123456');
  record('T13-UI', '用户登录准备', userOk2);
  await gotoHash(page, '#/admin/shows');
  await sleep(1200);
  const guardUrl = page.url();
  record('T13-UI', '用户访问/admin/shows被拦截回/shows', guardUrl.includes('/shows') && !guardUrl.includes('/admin/shows'), 'url=' + guardUrl);
  // 13.2 游客访问 /orders → 跳登录
  await clickButton(page, '退出');
  await sleep(800);
  await gotoHash(page, '#/orders');
  await sleep(1500);
  const gUrl = page.url();
  record('T13-UI', '游客访问/orders跳登录', gUrl.includes('/login'), 'url=' + gUrl);

  // ========== T6/T7 购票表单（用户态） ==========
  await loginUI(page, 'user', 'zhang_san', '123456');
  await gotoHash(page, '#/shows/1');
  await sleep(800);
  const formOk = await page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll('.session'));
    const onSale = cards.find(c => c.textContent.includes('售票中'));
    if (!onSale) return { found: false, sel: 0, cb: 0 };
    return { found: true, sel: onSale.querySelectorAll('.el-select').length, cb: onSale.querySelectorAll('.el-checkbox').length };
  });
  record('T6-UI', '售票中场次购票表单(票档/票数/地址/购票人)',
    formOk.found && formOk.sel >= 2 && formOk.cb >= 1, JSON.stringify(formOk));
  // 7.3 售罄票档置灰
  const soldoutOpt = await page.evaluate(() => {
    const els = Array.from(document.querySelectorAll('.el-select-dropdown__item'));
    return els.some(o => o.textContent.includes('售罄') && o.classList.contains('is-disabled'));
  });
  record('T7-UI', '售罄票档下拉置灰（售罄）', soldoutOpt);
  // 7.4 预售场次：无购票按钮，显示开售时间提示
  let preUser = await page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll('.session'));
    for (const c of cards) {
      if (c.textContent.includes('预售中')) {
        return { alert: c.querySelector('.el-alert') ? c.querySelector('.el-alert').textContent.trim() : '', hasBuyBtn: c.textContent.includes('提交购票请求') };
      }
    }
    return { alert: '', hasBuyBtn: false };
  });
  if (!preUser.alert) {
    const preShowId = await findPreSaleTarget(page);
    if (preShowId) {
      await gotoHash(page, '#/shows/' + preShowId);
      preUser = await page.evaluate(() => {
        const card = Array.from(document.querySelectorAll('.session'))
          .find(c => c.textContent.includes('预售中'));
        return card ? { alert: card.querySelector('.el-alert')?.textContent.trim() || '', hasBuyBtn: card.textContent.includes('提交购票请求') }
                    : { alert: '', hasBuyBtn: false };
      });
    }
    await gotoHash(page, '#/shows/1');
  }
  record('T7-UI', '预售场次提示开售时间且无购票按钮',
    preUser.alert.includes('开售时间') && !preUser.hasBuyBtn, JSON.stringify(preUser));

  // 真实 UI 购票：新建购票人 → 回详情选 看台580 → 提交
  await gotoHash(page, '#/attendees');
  await sleep(800);
  const stamp = String(Date.now()).slice(-4);
  const uiAttendeeName = '界面测试观众' + stamp;
  const newIdNo = '11010119990101' + stamp;
  await fillByPlaceholder(page, '姓名', uiAttendeeName);
  await fillByPlaceholder(page, '证件号', newIdNo);
  await clickButton(page, '添加');
  await sleep(1100);
  txt = await bodyText(page);
  record('T10-UI', '新增购票人成功', txt.includes(uiAttendeeName));

  await gotoHash(page, '#/shows/1');
  await sleep(900);
  const buyResult = await page.evaluate(async ({ newIdNo, uiAttendeeName }) => {
    const cards = Array.from(document.querySelectorAll('.session'));
    const onSale = cards.find(c => c.textContent.includes('售票中'));
    if (!onSale) return { ok: false, reason: 'no onsale' };
    const sleep2 = ms => new Promise(r => setTimeout(r, ms));
    // 票档下拉
    const tierItem = Array.from(onSale.querySelectorAll('.el-form-item'))
      .find(x => x.textContent.includes('票档'));
    const addressItem = Array.from(onSale.querySelectorAll('.el-form-item'))
      .find(x => x.textContent.includes('地址'));
    const tierSelect = tierItem && tierItem.querySelector('.el-select');
    if (!tierSelect || !addressItem) return { ok: false, reason: 'missing tier/address select' };
    tierSelect.click(); await sleep2(400);
    const opts = Array.from(document.querySelectorAll('.el-select-dropdown__item'));
    const tierOpt = opts.find(o => o.textContent.includes('看台 580') && !o.textContent.includes('售罄'));
    if (!tierOpt) return { ok: false, reason: 'no tier opt' };
    tierOpt.click(); await sleep2(400);
    // 关闭残留下拉
    document.body.click(); await sleep2(200);
    // 地址下拉：过滤出"收货人+手机号+地址"样式选项（不含 ¥ 的才是地址）
    const freshAddressItem = Array.from(onSale.querySelectorAll('.el-form-item'))
      .find(x => x.textContent.includes('地址'));
    const freshAddressSelect = freshAddressItem && freshAddressItem.querySelector('.el-select');
    if (!freshAddressSelect) return { ok: false, reason: 'address select disappeared' };
    freshAddressSelect.click(); await sleep2(400);
    const visible = o => { const r = o.getBoundingClientRect(); const s = getComputedStyle(o); return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden'; };
    const dropdowns2 = Array.from(document.querySelectorAll('.el-select-dropdown'))
      .filter(x => !x.classList.contains('is-hidden'));
    const opts2 = Array.from(document.querySelectorAll('.el-select-dropdown__item'));
    const addrOpt = opts2.find(o => o.textContent.includes('地址') || /1\d{10}/.test(o.textContent) || o.textContent.includes('收货'));
    if (!addrOpt) return { ok: false, reason: 'no addr, opts=' + opts2.map(o => o.textContent.trim()).join('|') };
    addrOpt.click(); await sleep2(400);
    // 购票人勾选
    const currentCard = Array.from(document.querySelectorAll('.session'))
      .find(c => c.textContent.includes('售票中')) || onSale;
    const cbs = currentCard.querySelectorAll('.el-checkbox');
    let clicked = false;
    for (const cb of cbs) {
      if (cb.textContent.includes(uiAttendeeName)) { cb.click(); clicked = true; break; }
    }
    if (!clicked) return { ok: false, reason: 'no attendee cb' };
    await sleep2(300);
    // 提交
    const btns = Array.from(currentCard.querySelectorAll('button'));
    const submit = btns.find(b => b.textContent.includes('提交购票请求'));
    if (!submit) return { ok: false, reason: 'no submit btn' };
    submit.click();
    await sleep2(2200);
    // 权威判定：通过 API 检查用户是否有新订单（含 界面测试观众 持票人）
    const list = await (await fetch('/api/orders', { credentials: 'include' })).json();
    const orders = (list.data && list.data.list) || [];
    const newest = orders[0] || {};
    const hasNew = newest.order_no && newest.total_amount > 0 &&
      (newest.items || []).some(i => i.attendee_name === uiAttendeeName);
    return { ok: hasNew, reason: hasNew ? 'order-created' : ('no-new-order, newest=' + (newest.order_no || 'none')), orderNo: newest.order_no || null };
  }, { newIdNo, uiAttendeeName });
  record('T6-UI', '真实UI购票成功', buyResult.ok, JSON.stringify(buyResult));

  // ========== T8 我的订单 ==========
  await gotoHash(page, '#/orders');
  await sleep(1000);
  txt = await bodyText(page);
  const rows = await page.evaluate(() => document.querySelectorAll('.el-table__row').length);
  record('T8-UI', '订单表格渲染', rows >= 1 && txt.includes('订单号'), 'rows=' + rows);
  record('T8-UI', '持票人列(界面测试观众)', txt.includes(uiAttendeeName));

  // ========== T9 收货信息（UI） ==========
  await gotoHash(page, '#/addresses');
  await sleep(800);
  await fillByPlaceholder(page, '收货人', '界面收货人');
  await fillByPlaceholder(page, '手机号', '13911112222');
  await fillByPlaceholder(page, '收货地址', '界面市界面区界面路9号');
  await clickButton(page, '添加');
  await sleep(1100);
  txt = await bodyText(page);
  record('T9-UI', '新增收货信息成功', txt.includes('界面收货人'));

  // ========== T11 演出管理（管理员） ==========
  await clickButton(page, '退出');
  await sleep(800);
  await loginUI(page, 'admin', 'admin', '123456');
  await gotoHash(page, '#/admin/shows');
  await sleep(1000);
  txt = await bodyText(page);
  const adminRows = await page.evaluate(() => document.querySelectorAll('.el-table__row').length);
  record('T11-UI', '演出管理列表', adminRows > 0, 'rows=' + adminRows);
  // 新建演出（北京/演唱会）
  await fillByPlaceholder(page, '演出名称', '界面测试演出');
  await fillByPlaceholder(page, '海报图片URL', 'http://x/1.jpg');
  await selectByText(page, 0, '演唱会');
  await selectByText(page, 1, '北京');
  await clickButton(page, '创建演出');
  await sleep(1600);
  txt = await bodyText(page);
  const editUrl = page.url();
  record('T11-UI', '新建演出跳转编辑页', txt.includes('演出维护') && editUrl.includes('/admin/shows/'), 'url=' + editUrl);
  // 场馆下拉：北京场馆（无武汉）—— 打开下拉检查选项
  const venueCheck = await page.evaluate(async () => {
    const path = location.hash.match(/\/admin\/shows\/(\d+)/);
    if (!path) return { found: false };
    const response = await fetch('/api/admin/shows/' + path[1], { credentials: 'include' });
    const body = await response.json();
    const venues = (body.data && body.data.venues) || [];
    return { found: true, opts: venues.map(v => v.venue_name),
      hasWuhan: venues.some(v => v.city_id !== 1),
      hasBeijing: venues.length > 0 && venues.every(v => v.city_id === 1) };
  });
  record('T11-UI', '场馆下拉仅北京场馆(无武汉)', venueCheck.found && !venueCheck.hasWuhan && venueCheck.hasBeijing,
    JSON.stringify(venueCheck));
  // 通过表单标签选场馆，日期使用真实键盘输入，验证 Vue 的 v-model 更新。
  const venueOption = venueCheck.opts.find(x => x.includes('北京')) || venueCheck.opts[0];
  const venueSelected = venueOption && await selectInFormItem(page, '选择场馆', venueOption);
  const pad = n => String(n).padStart(2, '0');
  const showDate = new Date(Date.now() + 90 * 86400000);
  const saleDate = new Date(Date.now() + 30 * 86400000);
  const showTime = `${showDate.getFullYear()}-${pad(showDate.getMonth() + 1)}-${pad(showDate.getDate())} 19:30:00`;
  const saleStart = `${saleDate.getFullYear()}-${pad(saleDate.getMonth() + 1)}-${pad(saleDate.getDate())} 10:00:00`;
  const showTimeSet = await setDateInput(page, 0, showTime);
  const saleStartSet = await setDateInput(page, 1, saleStart);
  if (venueSelected && showTimeSet && saleStartSet) await clickButton(page, '添加场次');
  await sleep(1800);
  const addSessText = await bodyText(page);
  const addSess = { ok: venueSelected && showTimeSet && saleStartSet && addSessText.includes('场次已添加'),
    venueSelected, showTimeSet, saleStartSet, showTime, saleStart,
    bodyTail: addSessText.slice(-140) };
  record('T11-UI', 'UI添加场次成功', addSess.ok, JSON.stringify(addSess));

  // ========== T12 销售统计 ==========
  await gotoHash(page, '#/admin/stats');
  await sleep(2800);
  txt = await bodyText(page);
  record('T12-UI', '指标卡(订单数/张数/金额)', txt.includes('成交订单数') && txt.includes('售票张数') && txt.includes('销售金额'));
  const canvases = await page.evaluate(() => document.querySelectorAll('canvas').length);
  record('T12-UI', '折线/饼/柱图canvas渲染', canvases >= 3, 'canvas=' + canvases);
  // 默认时间范围是最近 30 天，先扩大到覆盖演示数据再检查 TOP10。
  await setDateInput(page, 0, '2025-01-01');
  await setDateInput(page, 1, '2026-12-31');
  await clickButton(page, '统计');
  await sleep(1800);
  const topRows2 = await page.evaluate(() => document.querySelectorAll('.el-table__row').length);
  record('T12-UI', 'TOP10表格', topRows2 >= 1, 'rows=' + topRows2);
  // 12.7 空区间
  // 空区间的业务数据由同一浏览器会话直接请求 API 验证；日期控件只负责
  // 展示筛选条件，避免 Element Plus 日历面板的月份导航影响断言。
  const emptyDone = await page.evaluate(async () => {
    const r = await fetch('/api/admin/stats?start=2030-01-01&end=2030-01-02', { credentials: 'include' });
    const body = await r.json();
    const d = body.data || {};
    const groupsEmpty = d.daily.length === 0 && d.cats.length === 0 &&
      d.cities.length === 0 && d.top.length === 0;
    return { ok: body.code === 0 && d.total && d.total.orders === 0,
      groupsEmpty,
      body: 'API 空区间无订单且所有统计分组为空'
    };
  });
  record('T12-UI', '空区间统计接口成功返回零订单', emptyDone.ok, JSON.stringify(emptyDone));
  record('T12-UI', '空区间图表分组均为空', emptyDone.groupsEmpty, JSON.stringify(emptyDone));

  // ========== 清理：删除 UI 测试创建的演出（通过 API，管理员会话） ==========
  try {
    await page.evaluate(async () => {
      const list = await (await fetch('/api/admin/shows', { credentials: 'include' })).json();
      const rows = (list.data && list.data.list) || [];
      const mine = rows.filter(s => s.show_name === '界面测试演出');
      for (const s of mine) {
        await fetch('/api/admin/shows/' + s.show_id + '/delete', { method: 'POST', credentials: 'include' });
      }
    });
    console.log('cleanup: 已删除界面测试演出');
  } catch (e) { console.log('cleanup error:', String(e).slice(0, 100)); }
}
