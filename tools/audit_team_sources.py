"""Audit every default team against cached exact recipes and reviewed video metadata.

No inference from a URL alone. Browser overrides are not touched by this script.
"""
import csv
import hashlib
import itertools
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO_TEAMS = {
    'BV1acXkBTE7s': [(['尤诺', '鉴心', '维里奈'], '')],
    'BV18JHE6ZESq': [(['尤诺', '琳奈', '守岸人'], ''), (['尤诺', '鉴心', '维里奈'], '')],
    'BV1V27y6hEfH': [(['嘉贝莉娜', '露帕', '莫宁'], '')],
    'BV1G4L96EEDr': [(['卡提希娅', '夏空', '漂泊者'], '气动')],
    'BV1krTu6DE8w': [(['赞妮', '菲比', '漂泊者'], '衍射')],
    'BV1uLKQ61Eo4': [(['陆·赫斯', '达妮娅', '莫宁'], '')],
    'BV1qHTi6JEYk': [(['绯雪', '洛瑟菈', '千咲'], '')],
    'BV1TuMA6VE7X': [(['赞妮', '菲比', '守岸人'], '')],
    'BV17huF6sEY4': [(['爱弥斯', '琳奈', '莫宁'], '')],
    'BV16i386JEZ9': [(['秧秧·玄翎', '千咲', '穗穗'], '')],
    'BV15E3s64E79': [(['绯雪', '洛瑟菈', '穗穗'], '')],
    'BV1UGNn6pE5d': [(['秧秧·玄翎', '莫宁', '千咲'], '')],
    'BV1D6gP6oEjz': [(['卡提希娅', '夏空', '千咲'], '')],
    'BV1q28m63E3s': [(['清宵', '达妮娅', '莫宁'], '')],
    'BV1Fu8h6YE8s': [(['嘉贝莉娜', '露帕', '达妮娅'], '')],
    'BV1uXYT6dEiQ': [(['景燃', '尤诺', '守岸人'], '')],
    'BV1VJYL6HEuQ': [(['景燃', '莫特斐', '守岸人'], ''), (['景燃', '莫特斐', '维里奈'], '')],
    'BV1CYYe6WEgV': [(['景燃', '丽贝卡', '守岸人'], '')],
    'BV11WaZ69E5H': [(['心', '今汐', '守岸人'], ''), (['心', '今汐', '卜灵'], '')],
    'BV1Qdny6NESS': [(['心', '锁暝', '守岸人'], ''), (['心', '锁暝', '卜灵'], '')],
}


def identity(members, attr=''):
    return tuple(sorted(members)), attr


def main():
    directory = ROOT / 'config/team_planner'
    teams = json.loads((directory / 'teams.json').read_text(encoding='utf-8'))
    by_identity = {identity(t['members'], t['rover_attribute']): t for t in teams}
    proof = defaultdict(list)
    rows = list(csv.DictReader((ROOT / 'character.csv').open(encoding='utf-8-sig')))
    names = {r['角色名称'] for r in rows}
    variants = {f'漂泊者·{attr}' for attr in ('衍射', '湮灭', '气动', '导电')}
    token = '(?:' + '|'.join(re.escape(n) for n in sorted(names | variants, key=len, reverse=True)) + ')'
    recipe = re.compile(rf'({token})\s*\+\s*({token})\s*\+\s*({token}(?:\s*/\s*{token})*)')
    for q in json.loads((ROOT / 'reference_analysis/matrix_teams/wiki_quotes.json').read_text(encoding='utf-8')):
        for match in recipe.finditer(q['quote']):
            for third in re.split(r'\s*/\s*', match[3]):
                raw = [match[1], match[2], third]
                attr = next((n.split('·')[-1] for n in raw if n.startswith('漂泊者·')), '')
                members = ['漂泊者' if n.startswith('漂泊者·') else n for n in raw]
                proof[identity(members, attr)].append(dict(kind='wiki', url=q['url'], quote=match[0]))
    for t in json.loads((directory / 'all_character_supplements.json').read_text(encoding='utf-8')):
        for quote in t.get('recommendation_quotes', []):
            proof[identity(t['members'], t['rover_attribute'])].append(dict(kind='guide', url=quote['source'], quote=quote['quote']))
    from tools.research_matrix_teams import NAMES
    workshop = json.loads((ROOT / 'tmp/team_research/workshop_teams.json').read_text(encoding='utf-8'))
    for source in workshop['teams']:
        members = [NAMES[n] for n in source['members']]
        for team in teams:
            if set(team['members']) != set(members):
                continue
            for code in source['codes']:
                desc = code.get('description', '')
                proof[identity(members, team['rover_attribute'])].append(dict(kind='workshop',
                    url=source['jsonUrl'], quote=desc, matrix=bool(re.search('矩阵|矩陣', desc))))
    added = []
    for bvid, combinations in VIDEO_TEAMS.items():
        path = ROOT / f'reference_analysis/bilibili/{bvid}.json'
        if not path.exists():
            continue
        video = json.loads(path.read_text(encoding='utf-8'))['data']
        quote = video['title'] + '\n' + video.get('desc', '')
        for members, attr in combinations:
            ident = identity(members, attr)
            # A non-matrix generic tutorial can corroborate an existing team,
            # but is not sufficient to add a brand-new matrix recommendation.
            matrix = bool(re.search('矩阵|矩陣', quote))
            if ident not in by_identity and matrix:
                key = hashlib.sha256(('|'.join(sorted(members)) + '|' + attr).encode()).hexdigest()[:16]
                team = dict(id=key, members=members, rover_attribute=attr, enabled=True, priority=2.5,
                    note='从B站标题/简介核对；未逐帧观看视频，链度及装备要求见原视频。', evidence='B站·矩阵教学',
                    sources=[], axes=[], selected_axis='', origin='bilibili_research')
                teams.append(team); by_identity[ident] = team; added.append(key)
            proof[ident].append(dict(kind='video', url=f'https://www.bilibili.com/video/{bvid}/', quote=quote,
                                    matrix=matrix, level='标题及简介，不是逐帧核实'))
    # These two clear three-character titles are already available in the first collection.
    collection = json.loads((ROOT / 'reference_analysis/bilibili/BV1acXkBTE7s.json').read_text(encoding='utf-8'))['data']
    for section in collection.get('ugc_season', {}).get('sections', []):
        for ep in section['episodes']:
            if ep['bvid'] in {'BV1Xf5u69EQg', 'BV1WvVZ6rEdP'}:
                proof[identity(['西格莉卡', '维里奈', '守岸人'])].append(dict(kind='video',
                    url=f"https://www.bilibili.com/video/{ep['bvid']}/", quote=ep['title'], matrix=True, level='合集标题'))
    # Public search page titles matched to exact three-role aliases; ambiguous
    # aliases require a separate metadata review before promotion.
    rechecked_ids = set()
    for filename in ('browser_verified.json', 'browser_resolved.json', 'browser_manual.json', 'browser_new_teams.json', 'browser_recheck_verified.json'):
        path = ROOT / 'reference_analysis/bilibili' / filename
        if not path.exists():
            continue
        for key, entry in json.loads(path.read_text(encoding='utf-8')).items():
            if filename == 'browser_recheck_verified.json':
                rechecked_ids.add(key)
            from tools.review_browser_evidence import title_matches, patterns
            for video in entry['videos']:
                if filename == 'browser_resolved.json' and not title_matches(video['title'], patterns(entry, True)):
                    continue
                proof[identity(entry['members'], entry['rover_attribute'])].append(dict(
                    kind='video', url=video['url'], quote=video['title'] + '\n' + video.get('description', ''),
                    matrix=True, level=video.get('resolution') or ('搜索页明确三人标题' if filename=='browser_verified.json' else '标题及简介全名复核')))
    overrides_path = directory / 'base_score_overrides.json'
    overrides = json.loads(overrides_path.read_text(encoding='utf-8')) if overrides_path.exists() else {}
    report = []
    for t in teams:
        matched = list({(p['kind'], p['url'], p.get('matrix', False)): p for p in proof[identity(t['members'], t['rover_attribute'])]}.values())
        videos = [x for x in matched if x['kind'] == 'video']
        wiki = [x for x in matched if x['kind'] == 'wiki']
        workshop = [x for x in matched if x['kind'] == 'workshop']
        matrix = any(x.get('matrix') for x in videos + workshop)
        base = 2.5 if any(x.get('matrix') for x in videos) else 2 if any(x.get('matrix') for x in workshop) else 1.5 if wiki else 1
        matrix_videos = [x for x in videos if x.get('matrix')]
        defaults_enabled = bool(matrix_videos or wiki or any(x.get('matrix') for x in workshop))
        disputed = set(t['members']) == {'尤诺', '琳奈', '鉴心'}
        if t['id'] in overrides:
            base = overrides[t['id']]['score']
            t['base_score_override'] = overrides[t['id']]
        t['priority'] = t['default_priority'] = base
        t['enabled'] = t['default_enabled'] = defaults_enabled
        t['source_audit'] = {'version': '2026-10-26-v5-disabled-recheck', 'matched': matched,
            'recheck_confirmed': t['id'] in rechecked_ids,
            'video_status': '已匹配矩阵视频标题/简介' if matrix_videos else '有通用视频，未匹配矩阵证据' if videos else '本轮搜索未匹配明确三人矩阵视频（不代表不存在）',
            'issue': '原提供视频实际介绍月琳守及月鉴维，不支持月琳鉴。' if disputed else '',
            'matrix_confirmed': matrix,
            'default_status_reason': '' if defaults_enabled else '暂无B站矩阵视频、工坊矩阵或Wiki明确配队证据，默认不参与'}
        for item in matched:
            if item['url'] not in t['sources']:
                t['sources'].append(item['url'])
        report.append({'id': t['id'], 'members': t['members'], 'rover_attribute': t['rover_attribute'],
                       'default_priority': base, 'default_enabled': defaults_enabled, **t['source_audit'],
                       'search_query': ' '.join(t['members']) + ' 矩阵 手法 教学'})
    (directory / 'teams.json').write_text(json.dumps(teams, ensure_ascii=False, indent=2), encoding='utf-8')
    (directory / 'catalogue.json').write_text(json.dumps(teams, ensure_ascii=False, indent=2), encoding='utf-8')
    reviewed = {t['id']: t for t in teams}
    supplements = json.loads((directory / 'pair_supplements.json').read_text(encoding='utf-8'))
    supplements = [reviewed.get(t['id'], t) for t in supplements]
    known = {t['id'] for t in supplements}
    supplements.extend(reviewed[k] for k in added if k not in known)
    (directory / 'pair_supplements.json').write_text(json.dumps(supplements, ensure_ascii=False, indent=2), encoding='utf-8')
    seed_path = ROOT / 'web/team_planner/seed.js'
    seed = json.loads(seed_path.read_text(encoding='utf-8').removeprefix('const PLANNER_SEED=').strip().removesuffix(';'))
    seed['teams'] = teams
    seed_path.write_text('const PLANNER_SEED=' + json.dumps(seed, ensure_ascii=False) + ';\n', encoding='utf-8')
    output = ROOT / 'reference_analysis/matrix_teams'
    (output / 'source_audit_all.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    with (output / 'source_audit_all.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['队伍', '属性', '默认基础分', '默认参与', '视频核查', '问题或停用原因', '搜索词'])
        for r in report:
            writer.writerow(['_'.join(r['members']), r['rover_attribute'], r['default_priority'], r['default_enabled'],
                             r['video_status'], r['issue'] or r['default_status_reason'], r['search_query']])
    print(json.dumps({'teams': len(teams), 'added': len(added), 'scores': Counter(t['priority'] for t in teams),
        'disabled_without_qualifying_evidence': sum(bool(r['default_status_reason']) for r in report),
        'video_matched': sum(bool([x for x in r['matched'] if x['kind'] == 'video']) for r in report)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
