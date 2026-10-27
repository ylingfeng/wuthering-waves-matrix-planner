"""Read each released character's public build guide and retain team evidence.

Uses public guide links discovered from the site's character index; parses
only three-column team sections, never arbitrary mentions in a page.
"""
import csv
import hashlib
import itertools
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from tools.research_matrix_teams import NAMES

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "tmp/team_research/all_character_guides"


def slug_mapping():
    mapping = {n.lower().replace(' ', '-').replace(':', ''): (cn, '') for n, cn in NAMES.items()}
    mapping.update({
        'suoming': ('锁暝', ''), 'luuk-herssen': ('陆·赫斯', ''),
        'xiangli-yao': ('相里要', ''), 'roccia': ('洛可可', ''), 'lumi': ('灯灯', ''),
        'encore': ('安可', ''), 'danjin': ('丹瑾', ''), 'lingyang': ('凌阳', ''),
        'yangyang': ('秧秧', ''), 'jianxin': ('鉴心', ''), 'yuanwu': ('渊武', ''),
        'taoqi': ('桃祈', ''), 'aalto': ('秋水', ''), 'yinlin': ('吟霖', ''),
        'rover': ('漂泊者', '衍射'), 'rover-electro': ('漂泊者', '导电'),
        'rover-havoc': ('漂泊者', '湮灭'), 'rover-aero': ('漂泊者', '气动'),
    })
    return mapping


def parse_teams(soup, mapping):
    anchor = soup.find(id='Team') or soup.find(id='team')
    if anchor is None:
        return []
    root = anchor.find_parent(class_='e-con-inner')
    if root is None:
        return []
    # Some pages put only the title in a boxed container, with teams adjacent.
    parent = root.find_parent(class_='e-parent')
    if parent is not None:
        root = parent
    results, seen = [], set()
    for row in root.select('.e-con-inner, .e-con, .elementor-container'):
        children = row.find_all(['div', 'section'], recursive=False)
        if len(children) != 3:
            continue
        columns = []
        for child in children:
            members = []
            for link in child.select('a[href*="/character/"]'):
                slug = urlsplit(link.get('href', '')).path.rstrip('/').split('/')[-1].removesuffix('-build')
                if slug in mapping and mapping[slug] not in members:
                    members.append(mapping[slug])
            columns.append(members)
        if not all(columns) or any(len(c) > 8 for c in columns):
            continue
        text = row.get_text(' ', strip=True)
        if not any(label in text for label in ('Main DPS', 'Sub DPS', 'Support', 'Healer')):
            continue
        # Keep the displayed team heading as evidence; Best != measured ranking.
        heading = row.find_previous(['h2', 'h3', 'h4'])
        title = heading.get_text(' ', strip=True) if heading else 'Team Comp'
        signature = repr(columns)
        if signature in seen:
            continue
        seen.add(signature)
        results.append({'heading': title, 'slots': columns, 'quote': text})
    return results


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    mapping = slug_mapping()
    if '--cached' in sys.argv:
        urls = [g['source'] for g in json.loads((CACHE / 'extracted.json').read_text(encoding='utf-8'))]
    else:
        index = requests.get('https://wutheringlab.com/', timeout=30)
        index.raise_for_status()
        soup = BeautifulSoup(index.content, 'html.parser')
        urls = sorted({a['href'] for a in soup.select('a[href*="/character/"]')
                       if urlsplit(a['href']).netloc == 'wutheringlab.com'})

    def fetch(url):
        slug = urlsplit(url).path.rstrip('/').split('/')[-1].removesuffix('-build')
        path = CACHE / (slug + '.html')
        if path.exists():
            content = path.read_bytes()
            status = 200
        else:
            try:
                response = requests.get(url, timeout=30)
                status = response.status_code
                content = response.content
                if status == 200:
                    path.write_bytes(content)
            except requests.RequestException as exc:
                return {'slug': slug, 'source': url, 'error': str(exc), 'teams': []}
        soup = BeautifulSoup(content, 'html.parser')
        return {'slug': slug, 'character': mapping.get(slug, ('未映射', ''))[0],
                'source': url, 'status': status,
                'teams': parse_teams(soup, mapping) if status == 200 else []}

    with ThreadPoolExecutor(max_workers=3) as pool:
        guides = list(pool.map(fetch, urls))
    (CACHE / 'extracted.json').write_text(json.dumps(guides, ensure_ascii=False, indent=2), encoding='utf-8')
    teams = {}
    rejected = []
    for guide in guides:
        for block in guide['teams']:
            for picks in itertools.product(*block['slots']):
                if mapping.get(guide['slug']) not in picks:
                    rejected.append({'source': guide['source'], 'slots': picks,
                                     'reason': '组合未包含攻略对应角色（含漂泊者属性），不作为该角色推荐'})
                    continue
                members = [p[0] for p in picks]
                if len(set(members)) != 3:
                    continue
                attr = next((p[1] for p in picks if p[0] == '漂泊者'), '')
                identity = '|'.join(sorted(members)) + '|' + attr
                key = hashlib.sha256(identity.encode()).hexdigest()[:16]
                if key not in teams:
                    teams[key] = {'id': key, 'members': members, 'rover_attribute': attr,
                                  'enabled': True, 'priority': 2, 'note': '',
                                  'evidence': '攻略·主流配队', 'sources': [], 'axes': [],
                                  'selected_axis': '', 'origin': 'all_character_research',
                                  'recommendation_quotes': []}
                item = teams[key]
                if guide['source'] not in item['sources']:
                    item['sources'].append(guide['source'])
                    item['recommendation_quotes'].append({'character': guide['character'],
                        'heading': block['heading'], 'quote': block['quote'], 'source': guide['source']})
                item['note'] = ('攻略原文：' + block['heading'] + ' / ' + block['quote'] +
                                '。按原文三列及替选展开；通用主流配队，不等于当前矩阵最强。初始队权2，可按实测调整。')
    output = ROOT / 'config/team_planner/all_character_supplements.json'
    output.write_text(json.dumps(list(teams.values()), ensure_ascii=False, indent=2), encoding='utf-8')
    (CACHE / 'rejected.json').write_text(json.dumps(rejected, ensure_ascii=False, indent=2), encoding='utf-8')
    print('页面', len(guides), '成功读取', sum(g.get('status') == 200 for g in guides),
          '有三列配队', sum(bool(g['teams']) for g in guides), '组合', len(teams))
    for guide in guides:
        print(guide.get('character', guide['slug']), len(guide['teams']),
              [b['slots'] for b in guide['teams']])


if __name__ == '__main__':
    main()
