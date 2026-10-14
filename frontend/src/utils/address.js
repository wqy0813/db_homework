// 智能收货地址解析：整段粘贴文本 → { 收货人, 手机号, 省市区代码, 详细地址 }
// 纯启发式规则（正则 + 行政区划最长匹配），不依赖外部 NLP 服务；
// 识别结果回填表单由用户核对后保存，容错优先。
import { regionData } from 'element-china-area-data'

// 常见标签前缀：如"收货人：张三"，先剥掉再解析
const LABELS = /(收货人|联系人|姓名|电话|手机|手机号|联系方式|地址|收货地址|所在地区)[:：]/g
// 分隔符：空格、中英文逗号顿号分号冒号句号
const SEPS = /[\s,，、;；]+/g
const SUFFIXES = ['壮族自治区', '回族自治区', '维吾尔自治区', '自治区', '特别行政区', '省', '市']
// 这些字出现说明"疑似人名"其实是地址开头
const ADDR_KEYWORDS = /[路街道巷号栋楼层室单元区县村镇湾岸]/

function stripSuffix(label) {
  for (const s of SUFFIXES) {
    if (label.length > s.length && label.endsWith(s)) return label.slice(0, -s.length)
  }
  return null
}

// 在 text 中查找 list 中出现的节点，名称最长的优先（避免"吉林市"被"吉林"抢先）
function matchIn(text, list) {
  let best = null
  for (const node of (list || [])) {
    const names = [node.label, stripSuffix(node.label)].filter(Boolean)
    for (const n of names) {
      const i = text.indexOf(n)
      if (i >= 0 && (!best || n.length > best.len)) best = { node, index: i, len: n.length }
    }
  }
  return best
}

export function parseSmartAddress(raw) {
  const out = { name: '', phone: '', region: [], regionText: '', detail: '' }
  const text = String(raw || '').replace(LABELS, ' ').replace(/\s+/g, ' ').trim()
  if (!text) return out

  // 1) 手机号：1 开头 11 位（第二位 3-9）
  const pm = text.match(/1[3-9]\d{9}/)
  if (pm) out.phone = pm[0]
  const rest = pm ? (text.slice(0, pm.index) + ' ' + text.slice(pm.index + pm[0].length)) : text

  // 2) 省 → 市 → 区 逐级匹配（中文地址默认按此顺序书写）
  let provNode = null, cityNode = null, distNode = null
  let regionStart = -1, regionEnd = -1
  const prov = matchIn(rest, regionData)
  if (prov) {
    provNode = prov.node
    regionStart = prov.index
    regionEnd = prov.index + prov.len
    const cities = provNode.children || []
    const cityMatch = matchIn(rest.slice(regionEnd), cities)
    if (cityMatch) {
      cityNode = cityMatch.node
      regionEnd += cityMatch.index + cityMatch.len
    } else if (cities.length === 1 && (cities[0].label === '市辖区' || cities[0].label === '县')) {
      // 直辖市/直辖县：文本里通常省略"市辖区"这一层
      cityNode = cities[0]
    }
    if (cityNode) {
      const distMatch = matchIn(rest.slice(regionEnd), cityNode.children || [])
      if (distMatch) {
        distNode = distMatch.node
        regionEnd += distMatch.index + distMatch.len
      }
    }
  } else {
    // 没写省：跨省搜市名，再回溯出所属省
    outer: for (const p of regionData) {
      for (const c of (p.children || [])) {
        const m = matchIn(rest, [c])
        if (m) {
          provNode = p
          cityNode = c
          regionStart = m.index
          regionEnd = m.index + m.len
          const dm = matchIn(rest.slice(regionEnd), c.children || [])
          if (dm) { distNode = dm.node; regionEnd += dm.index + dm.len }
          break outer
        }
      }
    }
  }

  if (provNode) {
    out.region = [provNode.value, cityNode && cityNode.value, distNode && distNode.value]
      .filter(v => v !== undefined && v !== null && v !== false)
    out.regionText = [provNode.label, cityNode && cityNode.label, distNode && distNode.label]
      .filter(l => l && l !== '市辖区' && l !== '县').join(' ')
  }

  // 3) 收货人：地区之前的短片段（无数字、无地址关键词才算人名）
  const before = (regionStart >= 0 ? rest.slice(0, regionStart) : '').replace(SEPS, ' ').trim()
  const after = rest.slice(regionEnd).replace(SEPS, ' ').trim()
  if (before && before.length <= 20 && !/\d/.test(before) && !ADDR_KEYWORDS.test(before)) {
    out.name = before
    out.detail = after
  } else {
    out.detail = [before, after].filter(Boolean).join(' ')
  }

  // 4) 完全没识别到地区时的兜底：第一个短词（无数字）当收货人
  if (!provNode) {
    const parts = rest.replace(SEPS, ' ').trim().split(' ').filter(Boolean)
    if (parts.length >= 1 && parts[0].length <= 4 && !/\d/.test(parts[0])) {
      out.name = parts[0]
      out.detail = parts.slice(1).join(' ')
    } else {
      out.detail = parts.join(' ')
    }
  }

  out.detail = out.detail.replace(/\s{2,}/g, ' ').trim().slice(0, 100)
  return out
}
