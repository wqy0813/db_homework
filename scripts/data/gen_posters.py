# -*- coding: utf-8 -*-
"""为每个巡演生成专属海报。
优先使用 backend/static/img/artists 下与主演匹配的真实图片，再回退到分类场景图。
输出到 backend/static/img/posters/<series_id>.jpg，并把 series.poster_url 指向它。
运行：python scripts/data/gen_posters.py
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))
import pymysql
from config import DB_CONFIG  # noqa: E402

IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend', 'static', 'img')
OUT_DIR = os.path.join(IMG_DIR, 'posters')
os.makedirs(OUT_DIR, exist_ok=True)

# 中文字体（微软雅黑）
FONT_BD = r'C:\Windows\Fonts\msyhbd.ttc'
FONT = r'C:\Windows\Fonts\msyh.ttc'

# 类型 -> 候选背景图（按类型从真实图里选，多个轮换避免雷同）
CAT_BG = {
    1: ['concert1.jpg', 'concert2.jpg', 'concert3.jpg'],
    2: ['theater1.jpg', 'theater2.jpg'],
    3: ['basket1.jpg', 'basket2.jpg'],
    4: ['kids1.jpg', 'kids2.jpg'],
    5: ['museum1.jpg', 'theater2.jpg'],
    6: ['piano1.jpg', 'piano2.jpg'],
    7: ['dance1.jpg', 'dance2.jpg'],
}

# 类型 -> 主色（海报强调色）
CAT_COLOR = {
    1: (233, 75, 100),   # 玫红（演唱会）
    2: (150, 84, 200),   # 紫（话剧）
    3: (59, 127, 255),   # 蓝（体育）
    4: (250, 173, 20),   # 橙（儿童）
    5: (59, 127, 255),   # 蓝（展览）
    6: (24, 144, 255),   # 蓝（音乐会）
    7: (255, 85, 85),    # 红（舞蹈）
}

POSTER_W, POSTER_H = 400, 560

# 已审核的本地真实素材。文件不存在时会自动跳过，不会阻断整批海报生成。
ARTIST_IMAGES = {
    '周杰伦': '周杰伦.jpg',
    '陈奕迅': '陈奕迅.jpg',
    '邓紫棋': '邓紫棋.webp',
    '郎朗': '郎朗.jpg',
    '李荣浩': '李荣浩.jpg',
    '梁静茹': '梁静茹.jpg',
    '刘德华': '刘德华.jpg',
    '王菲': '王菲.jpg',
    '王羽佳': '王羽佳.jpg',
    'CBA': 'CBA联赛.jpg',
    'Taylor Swift': 'Taylor_Swift.jpg',
    '小猪佩奇': '小猪佩奇.jpg',
    '海底小纵队': '海底小纵队.jpg',
}


def find_artist_image(artist, series_name):
    """按主演名匹配真实图片；兼容主唱字段为空但系列名含艺人的情况。"""
    text = '%s %s' % (artist or '', series_name or '')
    artist_dir = os.path.join(IMG_DIR, 'artists')
    for keyword, filename in sorted(ARTIST_IMAGES.items(), key=lambda item: len(item[0]), reverse=True):
        if keyword in text:
            path = os.path.join(artist_dir, filename)
            if os.path.isfile(path):
                return path
    return None


def wrap_text(text, font, max_w):
    """按像素宽度折行。"""
    lines = []
    cur = ''
    for ch in text:
        if font.getlength(cur + ch) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def make_poster(series_id, series_name, artist, cat, bg_pool):
    # 1) 背景：缩放填满
    artist_path = find_artist_image(artist, series_name)
    if artist_path:
        bg_path = artist_path
    else:
        bg_name = bg_pool[series_id % len(bg_pool)]
        bg_path = os.path.join(IMG_DIR, bg_name)
    bg = Image.open(bg_path).convert('RGB')
    # 居中裁剪到海报比例再缩放
    ratio = POSTER_W / POSTER_H
    bw, bh = bg.size
    if bw / bh > ratio:
        nh = bh
        nw = int(bh * ratio)
    else:
        nw = bw
        nh = int(bw / ratio)
    x0, y0 = (bw - nw) // 2, (bh - nh) // 2
    bg = bg.crop((x0, y0, x0 + nw, y0 + nh)).resize((POSTER_W, POSTER_H), Image.LANCZOS)
    # 分类背景轻微模糊增强文字可读性；艺人真实照片保持清晰，避免失去辨识度。
    if not artist_path:
        bg = bg.filter(ImageFilter.GaussianBlur(1.2))
    img = bg.convert('RGBA')

    draw = ImageDraw.Draw(img)
    color = CAT_COLOR.get(cat, (60, 60, 60))

    # 2) 底部 + 顶部渐变遮罩（保证文字可读）
    overlay = Image.new('RGBA', (POSTER_W, POSTER_H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for y in range(POSTER_H):
        a = 0
        if y > POSTER_H * 0.45:
            a = int(200 * ((y - POSTER_H * 0.45) / (POSTER_H * 0.55)))
        if y < POSTER_H * 0.18:
            a = max(a, int(140 * (1 - y / (POSTER_H * 0.18))))
        if a:
            od.line([(0, y), (POSTER_W, y)], fill=(10, 10, 20, min(a, 215)))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # 3) 类型角标（左上）
    cat_font = ImageFont.truetype(FONT, 22)
    cat_text = {1: '演唱会', 2: '话剧歌剧', 3: '体育', 5: '展览', 6: '音乐会', 7: '舞蹈芭蕾'}.get(cat, '')
    draw.rounded_rectangle((16, 16, 16 + cat_font.getlength(cat_text) + 24, 52), radius=18, fill=color)
    draw.text((28, 24), cat_text, font=cat_font, fill=(255, 255, 255))

    # 4) 底部：主演名（大字）+ 巡演名
    if artist:
        artist_font = ImageFont.truetype(FONT_BD, 44)
        draw.text((22, POSTER_H - 150), artist, font=artist_font, fill=(255, 255, 255))
    name_font = ImageFont.truetype(FONT_BD, 26)
    lines = wrap_text(series_name, name_font, POSTER_W - 44)
    y = POSTER_H - 140 - (len(lines) * 34)
    for line in lines[:3]:
        draw.text((22, y), line, font=name_font, fill=(255, 255, 255))
        y += 34
    # 小横线装饰
    draw.rectangle((22, POSTER_H - 24, 110, POSTER_H - 20), fill=color)

    out = os.path.join(OUT_DIR, '%d.jpg' % series_id)
    img.convert('RGB').save(out, 'JPEG', quality=88)
    return '/static/img/posters/%d.jpg' % series_id


def main():
    conn = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT series_id, series_name, main_artist, category_id FROM show_series")
    rows = cur.fetchall()
    print('巡演数:', len(rows))
    n = 0
    for r in rows:
        url = make_poster(r['series_id'], r['series_name'], r['main_artist'],
                          r['category_id'], CAT_BG.get(r['category_id'], ['concert1.jpg']))
        cur.execute("UPDATE show_series SET poster_url=%s WHERE series_id=%s", (url, r['series_id']))
        n += 1
    conn.commit()
    print('已生成并更新海报:', n, '张')
    # 验证
    cur.execute("SELECT COUNT(*) AS c FROM show_series WHERE poster_url LIKE '/static/img/posters/%'")
    print('指向专属海报的巡演:', cur.fetchone()['c'])
    conn.close()


if __name__ == '__main__':
    main()
