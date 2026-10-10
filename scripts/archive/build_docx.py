# -*- coding: utf-8 -*-
"""
将《演出门票销售系统_数据库设计.md》预处理为适合 pandoc 转 Word 的中间稿：
1. 加封面（课程设计信息表）；
2. 加 Word 目录域（在 Word 中按 F9 / 右键“更新域”生成目录）；
3. Mermaid 代码块替换为插图占位说明（Word 不能直接渲染 Mermaid，
   源图保留在 .md 文件中，可用 VS Code/Typora 预览后截图粘贴）。
运行：python build_docx.py，然后执行 pandoc 命令（见脚本末尾注释）。
"""
import io
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'docs', '演出门票销售系统_数据库设计.md')
OUT = os.path.join(ROOT, 'docs', 'test-results', 'report_for_docx.md')

body = io.open(SRC, encoding='utf-8').read()

# ---- 3. Mermaid 块替换为插图占位 -------------------------------------------
captions = [
    '图 1　购票业务流程图（Mermaid 源图见随附 .md 文件：可用 VS Code/Typora 打开预览后截图粘贴于此）',
    '图 2　顶层数据流图（上下文图）（Mermaid 源图见随附 .md 文件，截图粘贴于此）',
    '图 3　0 层 / 1 层数据流图（Mermaid 源图见随附 .md 文件，截图粘贴于此）',
    '图 4　全局 E-R 图（Mermaid 源图见随附 .md 文件，截图粘贴于此）',
]
state = {'i': 0}

def repl(_m):
    cap = captions[min(state['i'], len(captions) - 1)]
    state['i'] += 1
    return '\n> **【%s】**\n' % cap

body = re.sub(r'```mermaid.*?```', repl, body, flags=re.S)

# ---- 1/2. 封面 + 分页 + 目录域 ---------------------------------------------
PAGE_BREAK = '\n```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```\n'

TOC_FIELD = (
    '\n```{=openxml}\n'
    '<w:p><w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>'
    '<w:r><w:instrText xml:space="preserve"> TOC \\o "1-3" \\h \\z \\u </w:instrText></w:r>'
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    '<w:r><w:t>打开本文件后，按 Ctrl+A 再按 F9（或右键此处选“更新域”）即可自动生成目录。</w:t></w:r>'
    '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>\n'
    '```\n'
)

cover = '''
**《数据库原理与应用》课程设计报告**

# 演出门票销售系统数据库设计

| 项　目 | 内　容 |
|---|---|
| 课程名称 | 数据库原理与应用 / 数据库系统课程设计 |
| 设计题目 | 演出门票销售系统数据库设计 |
| 设计内容 | 需求分析 → 概念设计 → 逻辑设计 → 物理设计（关系数据库，MySQL 8.0） |
| 学院（系） | 　 |
| 专　　业 | 　 |
| 班　　级 | 　 |
| 学　　号 | 　 |
| 姓　　名 | 　 |
| 指导教师 | 　 |
| 完成日期 | 　 |

> 附：物理建库脚本 `ddl.sql`、测试数据脚本 `seed_data.sql`、典型业务与统计查询脚本 `queries.sql`。
'''

out = cover + PAGE_BREAK + '## 目录\n' + TOC_FIELD + PAGE_BREAK + body

io.open(OUT, 'w', encoding='utf-8').write(out)
print('OK ->', OUT, '; mermaid blocks replaced:', state['i'])

# 生成 Word：
#   pandoc report_for_docx.md -f markdown+pipe_tables -o 演出门票销售系统_课程设计报告.docx
