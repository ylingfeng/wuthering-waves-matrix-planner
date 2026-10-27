"""Resumable, bounded per-team public search. Stop on access/rate limits.

Search hits are leads, not automatically verified three-person recommendations.
"""
import argparse
import json
from pathlib import Path
import time
import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()
    teams = json.loads((ROOT / 'config/team_planner/teams.json').read_text(encoding='utf-8'))
    path = ROOT / 'reference_analysis/bilibili/team_search_queue.json'
    previous = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    for t in teams:
        previous.setdefault(t['id'], {'members': t['members'], 'rover_attribute': t['rover_attribute'],
            'query': '鸣潮 ' + ' '.join(t['members']) + ' 矩阵 手法 教学', 'status': 'pending'})
    count = 0
    for t in teams:
        row = previous[t['id']]
        if row['status'] == 'searched' or count >= args.limit:
            continue
        count += 1
        try:
            response = requests.get('https://api.bilibili.com/x/web-interface/search/type',
                params={'search_type': 'video', 'keyword': row['query']},
                headers={'User-Agent': 'matrix-team-research/1.0'}, timeout=20)
            row['http_status'] = response.status_code
            if response.status_code != 200:
                row['status'] = 'access_limited'
                break
            data = response.json()
            if data.get('code') != 0:
                row.update(status='access_limited', api_code=data.get('code'))
                break
            row['results'] = [{'bvid': v.get('bvid'), 'title': v.get('title'), 'description': v.get('description'),
                               'author': v.get('author')} for v in data.get('data', {}).get('result', []) if v.get('bvid')]
            row['status'] = 'searched'
            print(row['query'], len(row['results']), flush=True)
        except (requests.RequestException, ValueError) as exc:
            row.update(status='error', error=str(exc))
            break
        finally:
            path.write_text(json.dumps(previous, ensure_ascii=False, indent=2), encoding='utf-8')
        time.sleep(1)
    path.write_text(json.dumps(previous, ensure_ascii=False, indent=2), encoding='utf-8')
    print('本次请求', count, '已取得结果', sum(v['status'] == 'searched' for v in previous.values()),
          '总队伍', len(teams))


if __name__ == '__main__':
    main()
