# -*- coding: utf-8 -*-
"""从 Bing 图片搜索下载明星/主演图到本地图库（第 4 期方案 C+）。
用法：
  1) python scripts/fetch_artist_images.py  --dry   只搜索不下载，打印将下载的 URL
  2) python scripts/fetch_artist_images.py          下载到 backend/static/img/artists/
下载后手动检查图片质量，再执行：
  3) python scripts/data/gen_posters.py              重新生成海报（背景用明星图）
注意：明星图片仅供课设演示使用（非商用），请勿用于公开传播。
"""
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))

# 默认直连；需要代理时可通过 IMAGE_PROXY=http://host:port 指定。
PROXY = os.environ.get('IMAGE_PROXY', '').strip()
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend', 'static', 'img', 'artists')
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'}

# 明星/主演 -> Bing 搜索词（可加"演唱会/演出/海报"提升命中）
ARTISTS = {
    '周杰伦': '周杰伦 演唱会 高清',
    '张学友': '张学友 演唱会 高清',
    '林俊杰': '林俊杰 演唱会 高清',
    '五月天': '五月天 演唱会 高清',
    '陈奕迅': '陈奕迅 演唱会 高清',
    '王菲': '王菲 演唱会 高清',
    '薛之谦': '薛之谦 演唱会 高清',
    '邓紫棋': '邓紫棋 演唱会 高清',
    '李荣浩': '李荣浩 演唱会 高清',
    '华晨宇': '华晨宇 演唱会 高清',
    '刘德华': '刘德华 演唱会 高清',
    '梁静茹': '梁静茹 演唱会 高清',
    '蔡依林': '蔡依林 演唱会 高清',
    '毛不易': '毛不易 演唱会 高清',
    '张杰': '张杰 演唱会 高清',
    '郎朗': '郎朗 钢琴 演奏',
    '王羽佳': '王羽佳 钢琴 演奏',
    '久石让': '久石让 音乐会',
    'Taylor Swift': 'Taylor Swift concert',
    'CBA联赛': 'CBA 篮球 比赛',
    '中超': '中超 足球 比赛',
    '莫奈': '莫奈 睡莲 油画',
    '梵高': '梵高 星空 油画',
    '茶馆': '话剧 茶馆',
    '暗恋桃花源': '话剧 暗恋桃花源',
    '白鹿原': '话剧 白鹿原',
    '戏台': '话剧 戏台',
    '歌剧魅影': '歌剧魅影 音乐剧',
    '巴黎圣母院': '巴黎圣母院 音乐剧',
    '雷雨': '话剧 雷雨',
    '小猪佩奇': '小猪佩奇',
    '奥特曼': '奥特曼 舞台剧',
    '熊出没': '熊出没 儿童剧',
    '汪汪队': '汪汪队立大功',
    '超级飞侠': '超级飞侠',
    '海底小纵队': '海底小纵队',
    'teamLab': 'teamLab 光 艺术展',
    '故宫': '故宫 文物 展览',
    '敦煌': '敦煌 壁画 艺术展',
    '恐龙': '恐龙 化石 展览',
    '太空': '太空 展览 科技馆',
    '天鹅湖': '芭蕾舞 天鹅湖',
    '胡桃夹子': '芭蕾舞 胡桃夹子',
    '朱鹮': '舞剧 朱鹮',
    '只此青绿': '只此青绿 舞剧',
}


def bing_search(query, n=6):
    """返回 Bing 图片搜索结果的 murl 列表（原图直链）。"""
    q = urllib.parse.quote(query)
    url = f'https://www.bing.com/images/async?q={q}&first=0&count={n}'
    req = urllib.request.Request(url, headers=HEADERS)
    if PROXY:
        req.set_proxy(PROXY.replace('http://', ''), 'http')
        req.set_proxy(PROXY.replace('http://', ''), 'https')
    with urllib.request.urlopen(req, timeout=25) as resp:
        html = resp.read().decode('utf-8', 'ignore')
    murls = re.findall(r'murl&quot;:&quot;(.*?)&quot;', html)
    if not murls:
        murls = re.findall(r'murl":"(.*?)"', html)
    # 去重、过滤
    out = []
    for m in murls:
        m = m.replace('\\/', '/')
        if m not in out:
            out.append(m)
    return out


def download(url, path, timeout=12):
    req = urllib.request.Request(url, headers={'User-Agent': HEADERS['User-Agent'], 'Referer': 'https://www.bing.com/'})
    if PROXY:
        req.set_proxy(PROXY.replace('http://', ''), 'http')
        req.set_proxy(PROXY.replace('http://', ''), 'https')
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(path, 'wb') as f:
        f.write(resp.read())
    # 校验是否真图片
    try:
        from PIL import Image
        im = Image.open(path)
        im.verify()
        return True, os.path.getsize(path)
    except Exception:
        return False, 0


def main():
    dry = '--dry' in sys.argv
    force = '--force' in sys.argv
    os.makedirs(OUT_DIR, exist_ok=True)
    print('Bing 搜索下载明星/主演图 ->', OUT_DIR)
    ok_cnt = 0
    fail = []
    for artist, query in ARTISTS.items():
        try:
            murls = bing_search(query)
        except Exception as e:
            print(f'  [搜索失败] {artist}: {e}')
            fail.append(artist)
            continue
        if not murls:
            print(f'  [无结果] {artist} ({query})')
            fail.append(artist)
            continue
        # 取第一个可用图
        got = False
        for i, u in enumerate(murls):
            ext = '.jpg'
            low = u.lower().split('?')[0]
            if low.endswith('.png'): ext = '.png'
            elif low.endswith('.webp'): ext = '.webp'
            path = os.path.join(OUT_DIR, '%d%s' % (hash(artist) % 100000, ext))
            # 用中文名做文件名更直观：映射到安全文件名
            safe = artist.replace(' ', '_').replace('.', '')
            path = os.path.join(OUT_DIR, safe + ext)
            existing = [os.path.join(OUT_DIR, safe + candidate) for candidate in ('.jpg', '.jpeg', '.png', '.webp')]
            if not dry and not force and any(os.path.isfile(p) and os.path.getsize(p) > 1024 for p in existing):
                print(f'  [SKIP] {artist} 已有本地素材')
                got = True
                break
            if dry:
                print(f'  [DRY] {artist} -> {path}  <- {u[:90]}')
                got = True
                break
            try:
                ok, size = download(u, path)
                if ok:
                    print(f'  [OK] {artist} -> {os.path.basename(path)} ({size//1024}KB)')
                    ok_cnt += 1
                    got = True
                    break
                else:
                    print(f'  [非图片] {artist} 尝试下一个')
            except Exception as e:
                print(f'  [下载失败] {artist}: {str(e)[:80]} 尝试下一个')
            time.sleep(0.2)
        if not got and not dry:
            fail.append(artist)
    print('---- 汇总 ----')
    if dry:
        print('DRY 模式：以上为将下载的图。去掉 --dry 执行下载。')
    else:
        print(f'成功 {ok_cnt} / {len(ARTISTS)}，失败 {len(fail)}: {fail}')


if __name__ == '__main__':
    main()
