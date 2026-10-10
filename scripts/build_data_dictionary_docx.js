const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  WidthType, BorderStyle, ShadingType, VerticalAlign, HeadingLevel,
  TableLayoutType
} = require('C:/Users/wqy/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/docx');

const root = path.resolve(__dirname, '..');
const sourcePath = path.join(root, 'docs', '演出门票销售系统_数据库设计对应内容.md');
const outputPath = path.join(root, 'docs', '演出门票销售系统_数据字典_紧凑版.docx');
const markdown = fs.readFileSync(sourcePath, 'utf8');

function parseCells(line) {
  return line.split('|').slice(1, -1).map(v => v.trim().replace(/^`|`$/g, ''));
}

function parseDictionarySections(text) {
  const re = /^### 3\.(\d+)\s+(.+)$/gm;
  const heads = [...text.matchAll(re)];
  return heads.map((match, index) => {
    const start = match.index + match[0].length;
    const nextDictionary = index + 1 < heads.length ? heads[index + 1].index : text.length;
    const after = text.slice(start);
    const nextTopHeadingOffset = after.search(/^##\s/m);
    const nextTopHeading = nextTopHeadingOffset >= 0 ? start + nextTopHeadingOffset : text.length;
    const end = Math.min(nextDictionary, nextTopHeading);
    const body = text.slice(start, end);
    const lines = body.split(/\r?\n/).filter(line => line.trim().startsWith('|'));
    const rows = lines.slice(2).map(parseCells).filter(row => row.length >= 3);
    return { number: Number(match[1]), heading: match[2].trim(), rows };
  });
}

const sections = parseDictionarySections(markdown);
const byTable = new Map();
sections.forEach(section => {
  const match = section.heading.match(/`([^`]+)`/);
  if (match) byTable.set(match[1], section);
});

const groups = [
  { title: '一、基础信息与账号表', tables: ['city', 'category', 'admin', 'app_user', 'venue'] },
  { title: '二、演出与票务资源表', tables: ['show_series', 'show_item', 'show_image', 'show_session', 'ticket_tier'] },
  { title: '三、用户资料表', tables: ['shipping_address', 'attendee'] },
  { title: '四、订单交易表', tables: ['ticket_order', 'order_item'] },
  { title: '五、购票请求与销售统计表', tables: ['purchase_request', 'sales_daily'] }
];

const colors = { ink: '19324A', blue: '2F75B5', muted: '63758A', border: '000000', highlight: 'FFF200' };
// Match the compact table proportions used by the reference document.
const tableWidth = 8296;
const columns = [1800, 1800, 2300, 2396];
const viewColumns = [1800, 2200, 4296];
const font = 'Microsoft YaHei';
const borders = {
  top: { style: BorderStyle.SINGLE, size: 4, color: colors.border },
  bottom: { style: BorderStyle.SINGLE, size: 4, color: colors.border },
  left: { style: BorderStyle.SINGLE, size: 4, color: colors.border },
  right: { style: BorderStyle.SINGLE, size: 4, color: colors.border },
  insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: colors.border },
  insideVertical: { style: BorderStyle.SINGLE, size: 4, color: colors.border }
};

function run(value, opts = {}) {
  return new TextRun({ text: String(value ?? ''), font: font, size: 20, color: colors.ink, ...opts });
}

function cellParagraph(value, opts = {}) {
  return new Paragraph({
    children: [run(value, opts)]
  });
}

function makeCell(value, width, opts = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    margins: { top: 0, bottom: 0, left: 45, right: 45 },
    verticalAlign: VerticalAlign.CENTER,
    children: [cellParagraph(value, opts)]
  });
}

function makeDataTable(rows) {
  const header = ['列名', '类型', '约束', '备注'];
  const tableRows = [
    new TableRow({
      tableHeader: true,
      cantSplit: true,
      children: header.map((value, i) => makeCell(value, columns[i], { bold: true, color: '111111' }))
    }),
    ...rows.map(row => new TableRow({
      cantSplit: true,
      children: [0, 1, 2, 3].map(i => makeCell(row[i] || '', columns[i]))
    }))
  ];
  return new Table({
    width: { size: tableWidth, type: WidthType.DXA },
    columnWidths: columns,
    layout: TableLayoutType.FIXED,
    borders,
    rows: tableRows
  });
}

function makeViewTable(rows) {
  const header = ['视图', '用途', '主要内容'];
  const tableRows = [
    new TableRow({
      tableHeader: true,
      cantSplit: true,
      children: header.map((value, i) => makeCell(value, viewColumns[i], { bold: true, color: '111111' }))
    }),
    ...rows.map(row => new TableRow({
      cantSplit: true,
      children: [0, 1, 2].map(i => makeCell(row[i] || '', viewColumns[i]))
    }))
  ];
  return new Table({
    width: { size: tableWidth, type: WidthType.DXA },
    columnWidths: viewColumns,
    layout: TableLayoutType.FIXED,
    borders,
    rows: tableRows
  });
}

function tableLabel(textValue) {
  return new Paragraph({
    keepNext: true,
    spacing: { before: 150, after: 70 },
    children: [run(`➢  ${textValue}`, { bold: true, size: 21, color: colors.ink })]
  });
}

function groupHeading(textValue) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 100 },
    keepNext: true,
    children: [run(textValue, { bold: true, size: 24, color: colors.blue })]
  });
}

const children = [];
children.push(new Paragraph({
  heading: HeadingLevel.HEADING_1,
  spacing: { before: 0, after: 100 },
  children: [run('3、数据字典', { bold: true, size: 30, color: colors.blue })]
}));
children.push(new Paragraph({
  spacing: { before: 0, after: 180 },
  children: [run('（包括各数据表中各列名称、类型、约束等详细说明）', { size: 22, highlight: 'yellow', color: '111111' })]
}));

groups.forEach(group => {
  children.push(groupHeading(group.title));
  group.tables.forEach(tableName => {
    const section = byTable.get(tableName);
    if (!section) throw new Error(`Missing dictionary section for ${tableName}`);
    children.push(tableLabel(section.heading));
    children.push(makeDataTable(section.rows));
    children.push(new Paragraph({ spacing: { after: 80 }, children: [] }));
  });
});

const viewSection = sections.find(section => section.number === 17);
children.push(groupHeading('六、业务视图'));
children.push(new Paragraph({
  spacing: { before: 0, after: 100 },
  children: [run('以下对象不是独立存储的基本关系，而是面向查询的逻辑视图。', { size: 20, color: colors.muted })]
}));
if (!viewSection) throw new Error('Missing view dictionary section');
children.push(makeViewTable(viewSection.rows));

children.push(new Paragraph({
  spacing: { before: 130, after: 50 },
  keepNext: true,
  children: [run('附注：分区表替代方案', { bold: true, size: 24, color: colors.blue })]
}));
children.push(new Paragraph({
  spacing: { before: 0, after: 0, line: 235 },
  children: [run('ticket_order_p 按 create_time 年分区，purchase_request_p 按 request_time 年分区；它们仅为大数据量替代方案，不属于当前主方案。MySQL 分区表不支持外键，参照完整性由应用层事务和对账作业保证。', { size: 16, color: colors.muted })]
}));

const doc = new Document({
  creator: '演出门票销售系统',
  title: '演出门票销售系统数据字典',
  description: '演出门票销售系统数据库数据字典',
  styles: {
    default: { document: { run: { font: font, size: 20, color: colors.ink } } }
  },
  sections: [{
    properties: {
      page: { margin: { top: 1440, bottom: 1440, left: 1800, right: 1800 } }
    },
    children
  }]
});

Packer.toBuffer(doc).then(buffer => fs.writeFileSync(outputPath, buffer));
