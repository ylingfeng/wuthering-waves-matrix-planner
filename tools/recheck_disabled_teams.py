"""Second-pass searches and conservative evidence review for disabled recipes."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tools import search_bilibili_browser as browser
from tools.review_browser_evidence import ALIASES, AMBIGUOUS

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'reference_analysis/bilibili'


def main():
    teams = json.loads((ROOT / 'config/team_planner/teams.json').read_text(encoding='utf-8'))
    seed = json.loads((ROOT / 'web/team_planner/seed.js').read_text(encoding='utf-8').removeprefix('const PLANNER_SEED=').strip().removesuffix(';'))
    characters = {c['name']: c for c in seed['characters']}
    snapshot = FOLDER / 'disabled_recheck_targets.json'
    if snapshot.exists():
        targets = json.loads(snapshot.read_text(encoding='utf-8'))
    else:
        targets = [t for t in teams if not t['default_enabled']]
        snapshot.write_text(json.dumps(targets, ensure_ascii=False, indent=2), encoding='utf-8')
    jobs = []
    for team in targets:
        members = sorted(team['members'], key=lambda n: 2 if characters[n]['healer'] else 0 if characters[n]['roles'] == ['主C'] else 1)
        def short(n):
            if n == '漂泊者':
                return {'衍射':'光','湮灭':'暗','气动':'风','导电':'雷'}[team['rover_attribute']]
            return AMBIGUOUS.get(n) or ALIASES.get(n, [n])[0]
        full = [n if n != '漂泊者' else team['rover_attribute'] + '漂泊者' for n in members]
        for suffix, query in [('short', ''.join(map(short, members)) + ' 矩阵'),
                              ('full', ' '.join(full) + ' 终焉矩阵 教学')]:
            jobs.append({**team, 'id':team['id']+'-'+suffix, 'search_query':query})
    browser.DEST = FOLDER / 'disabled_recheck_search'
    browser.DEST.mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(browser.worker, [jobs[::2], jobs[1::2]]))
    records = [json.loads(p.read_text(encoding='utf-8')) for p in browser.DEST.glob('*.json')]
    print(json.dumps({'teams':len(targets),'queries':len(jobs),'searched':sum(r['status']=='searched' for r in records)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
