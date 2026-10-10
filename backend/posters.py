"""Resolve collected originals by performance identity, independent of database IDs."""
import csv
import re
from pathlib import Path

from flask import Blueprint, abort, send_from_directory

COLLECT_DIR = Path(__file__).resolve().parents[1] / 'poster_collect'
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

# Short names used by the seed/data generators. Do not match arbitrary substrings
# (e.g. 猫 must not match a children's show containing the same character).
ALIASES = {
    'CBA 职业篮球联赛': (3, ['CBA', 'CBA联赛', 'CBA篮球联赛', 'CBA 常规赛']),
    '莫奈《光影》沉浸式艺术展': (5, ['莫奈沉浸展']),
    '梵高《星夜》光影艺术展': (5, ['梵高光影展']),
    'teamLab 无界美术馆': (5, ['teamLab无界']),
    '恐龙化石科普展': (5, ['恐龙化石展']),
    '太空探索沉浸展': (5, ['太空探索展']),
    '久石让·宫崎骏动漫音乐会': (6, ['久石让音乐会']),
    '王羽佳钢琴独奏音乐会': (6, ['王羽佳钢琴']),
    '郎朗钢琴独奏音乐会': (6, ['郎朗钢琴']),
    '猫': (2, ['音乐剧《猫》']),
}


def normalize_name(name):
    name = re.sub(r'·[^·]+站$', '', name or '')
    name = re.sub(r'^(?:芭蕾舞剧|音乐剧|话剧|舞剧)', '', name)
    return re.sub(r'[\s《》「」“”·]', '', name).casefold()


def load_catalog():
    catalog = {}
    for group in 'ABCD':
        source = COLLECT_DIR / group / 'sources.csv'
        if not source.is_file():
            continue
        with source.open(encoding='utf-8-sig', newline='') as file:
            for row in csv.DictReader(file):
                filename = row['file_name']
                if Path(filename).name != filename:
                    continue
                path = source.parent / filename
                if path.suffix.lower() not in IMAGE_EXTENSIONS or not path.is_file():
                    continue
                catalog[normalize_name(row['name'])] = f'/posters/{group}/{filename}'
    return catalog


CATALOG = load_catalog()


def collected_poster(name, category_id=None, artist=None):
    key = normalize_name(name)
    # Exact performance name, including short theatre titles without 《》.
    if key in CATALOG and not (key == '猫' and category_id != 2):
        return CATALOG[key]
    if category_id == 1:
        performer = normalize_name(artist or (name or '').split('《')[0])
        performer = re.sub(r'(?:世界)?(?:巡回|巡迴)?演唱会$', '', performer)
        url = CATALOG.get(performer + '巡回演唱会')
        if url:
            return url
    for title, (category, aliases) in ALIASES.items():
        if category_id == category and key in {normalize_name(alias) for alias in aliases}:
            return CATALOG.get(normalize_name(title))
    # CBA seed shows include the matchup after a colon.
    if category_id == 3 and re.match(r'^CBA\s*常规赛[：:]', name or '', re.I):
        return CATALOG.get(normalize_name('CBA 职业篮球联赛'))
    return None


def resolve_poster(name, category_id, current_url=None, artist=None):
    # Keep administrator uploads and explicitly configured external posters.
    if current_url and (current_url.startswith('/static/img/uploads/') or
                        current_url.startswith(('http://', 'https://'))):
        return current_url
    collected = collected_poster(name, category_id, artist)
    if collected:
        return collected
    # Legacy/generated local paths were removed; only URLs served by this app remain valid.
    if (current_url or '').startswith(('/img/', '/static/img/')):
        return None
    return current_url


posters_bp = Blueprint('posters', __name__)


@posters_bp.route('/posters/<group>/<filename>')
def poster_file(group, filename):
    if group not in 'ABCD' or len(group) != 1 or Path(filename).suffix.lower() not in IMAGE_EXTENSIONS:
        abort(404)
    # Serve the actual collected file rather than a generated/static copy.
    response = send_from_directory(str(COLLECT_DIR / group), filename)
    response.headers['Cache-Control'] = 'no-cache'
    return response
