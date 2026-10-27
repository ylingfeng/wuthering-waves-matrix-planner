"""Search each team using the public browser UI. Cache results, stop on challenges."""
import json
from pathlib import Path
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'reference_analysis/bilibili/browser_search'
STOP = threading.Event()


def worker(teams):
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
        page = browser.new_page()
        for team in teams:
            if STOP.is_set():
                break
            path = DEST / (team['id'] + '.json')
            if path.exists() and json.loads(path.read_text(encoding='utf-8')).get('status') == 'searched':
                continue
            members = [n if n != '漂泊者' else {'衍射':'光主','湮灭':'暗主','气动':'风主','导电':'雷主'}.get(team['rover_attribute'], n) for n in team['members']]
            query = team.get('search_query') or ' '.join(members) + ' 矩阵'
            result = dict(id=team['id'], members=team['members'], rover_attribute=team['rover_attribute'], query=query, status='pending')
            try:
                response = page.goto('https://search.bilibili.com/all?keyword=' + quote(query), wait_until='domcontentloaded', timeout=25000)
                page.wait_for_timeout(500)
                body = page.locator('body').inner_text()
                result['http_status'] = response.status if response else None
                if (response and response.status in (403, 412, 429)) or any(x in body for x in ('验证后继续访问', '请完成验证', '访问受限')):
                    result['status'] = 'access_limited'
                    STOP.set()
                else:
                    links = page.locator('a[href*="/video/BV"]').evaluate_all('(links)=>links.map(a=>({url:a.href,title:a.innerText.trim()}))')
                    videos = {}
                    for link in links:
                        match = re.search(r'BV[0-9A-Za-z]{10}', link['url'])
                        if not match or not re.search(r'[\u4e00-\u9fff]', link['title']):
                            continue
                        bvid = match.group()
                        if bvid not in videos or len(link['title']) > len(videos[bvid]['title']):
                            videos[bvid] = dict(bvid=bvid, title=link['title'], url=f'https://www.bilibili.com/video/{bvid}/')
                    result['results'] = list(videos.values())
                    result['status'] = 'searched' if videos or '没有找到' in body else 'empty_or_error'
                    result['page_title'] = page.title()
                    if not videos:
                        result['page_text'] = body[:1500]
                print(json.dumps({'id': team['id'], 'query': query, 'status': result['status'], 'results': len(result.get('results', []))}, ensure_ascii=False), flush=True)
            except Exception as exc:
                result.update(status='error', error=str(exc))
                print(team['id'], 'error', str(exc)[:80], flush=True)
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            time.sleep(.5)
        browser.close()


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    teams = json.loads((ROOT / 'config/team_planner/teams.json').read_text(encoding='utf-8'))
    # Two independent browser tabs at a modest rate; no retries on a challenge.
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(worker, [teams[::2], teams[1::2]]))
    records = [json.loads(p.read_text(encoding='utf-8')) for p in DEST.glob('*.json')]
    print('已记录', len(records), '搜索成功', sum(r['status']=='searched' for r in records), '总队伍', len(teams))


if __name__ == '__main__':
    main()
