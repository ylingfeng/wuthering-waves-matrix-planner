"""Review second-pass search results; resolve short-name collisions via public metadata."""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from tools.review_browser_evidence import ALIASES, AMBIGUOUS, clean, patterns, title_matches

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'reference_analysis/bilibili'
# Individually reviewed title boundaries: surrounding prose/score strings
# hide an otherwise explicit contiguous three-role code from strict matching.
REVIEWED_TITLES = {
    'BV1Ce8V6HELc', 'BV11vwczNE7N', 'BV1kZHK6VEGd', 'BV1rGKD6ZEgt',
    'BV1oMHT6iEYD', 'BV1XKSZBMEF6', 'BV1rS4d6hEeF', 'BV18XTc63EiV',
    'BV1VeGq6ZEbh', 'BV1qTJb6fE7B', 'BV1NmgF6qEgT', 'BV1MN5b6YE64',
    'BV1G9nJ6hEET', 'BV1c5HK6CEGE', 'BV1cynU6FExP', 'BV1joH36JEvW',
    'BV1HEogBgE9t', 'BV1ondaBWEwx', 'BV1EdHV6ZEiM', 'BV1W8aZ6DEjL',
    'BV1W9px6rEzW', 'BV1tmnV6gE7D',
}


def resolves_name(name, text):
    def variants(n):
        return [clean(a) for a in [n]+ALIASES.get(n,[]) if len(a)>1]
    # 秧秧·玄翎 contains 秧秧. Shared-shortname alternatives must not
    # accidentally corroborate the wrong character via substring matching.
    rivals = [n for n in AMBIGUOUS if n != name and AMBIGUOUS[n] == AMBIGUOUS[name]]
    for rival in rivals:
        for alias in variants(rival):
            if alias not in clean(name) and alias in text:
                return False
    return any(alias in text for alias in variants(name))


def metadata(video):
    bvid = video['bvid']
    path = FOLDER / (bvid + '.json')
    tags_path = FOLDER / (bvid + '.tags.json')
    headers = {'User-Agent':'matrix-team-research/1.0'}
    if path.exists():
        payload = json.loads(path.read_text(encoding='utf-8'))
    else:
        response = requests.get('https://api.bilibili.com/x/web-interface/view', params={'bvid':bvid}, headers=headers, timeout=15)
        response.raise_for_status()
        payload = response.json()
        if payload.get('code') == 0:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    data = payload.get('data') or {}
    if tags_path.exists():
        tags = json.loads(tags_path.read_text(encoding='utf-8'))
    else:
        response = requests.get('https://api.bilibili.com/x/tag/archive/tags', params={'bvid':bvid}, headers=headers, timeout=15)
        response.raise_for_status()
        payload = response.json()
        tags = [t['tag_name'] for t in payload.get('data',[]) or []] if payload.get('code') == 0 else []
        if payload.get('code') == 0:
            tags_path.write_text(json.dumps(tags, ensure_ascii=False, indent=2), encoding='utf-8')
    return data, tags


def review(team):
    merged = {}
    files = [FOLDER / 'browser_search' / (team['id']+'.json')]
    files += list((FOLDER / 'disabled_recheck_search').glob(team['id']+'-*.json'))
    for path in files:
        if path.exists():
            for v in json.loads(path.read_text(encoding='utf-8')).get('results',[]):
                merged[v['bvid']] = v
    exact, relaxed = patterns(team), patterns(team, True)
    matches, pending = [], []
    for video in merged.values():
        title = video['title']
        if re.search('求.*教|求.*指|求助|不会|没打出', title):
            continue
        matrix_title = bool(re.search('矩阵|矩陣', title))
        reviewed = video['bvid'] in REVIEWED_TITLES
        if matrix_title and (title_matches(title, exact) or reviewed and any(p in clean(title) for p in exact)):
            matches.append({**video, 'resolution':'矩阵标题明确三人全名或无歧义简称'})
        elif (title_matches(title, relaxed) or reviewed and any(p in clean(title) for p in relaxed)) and (matrix_title or re.search('教学|手法|攻略|轮椅|轴', title)):
            pending.append(video)
    pending.sort(key=lambda v:not bool(re.search('教学|手法|攻略|轮椅|轴',v['title'])))
    failures = []
    for video in pending[:8]:
        if len(matches) >= 3:
            break
        try:
            data, tags = metadata(video)
            raw_text = data.get('title',video['title'])+' '+data.get('desc','')+' '.join(tags)
            if not re.search('矩阵|矩陣', raw_text):
                continue
            text = clean(raw_text)
            ambiguous = [n for n in team['members'] if n in AMBIGUOUS]
            if all(resolves_name(n, text) for n in ambiguous):
                matches.append({**video,'description':data.get('desc','')+'\n视频标签：'+'、'.join(tags), 'resolution':'明确三人简称＋简介/标签全名消歧'})
        except (requests.RequestException, ValueError, KeyError) as exc:
            failures.append({'bvid':video['bvid'],'error':str(exc)[:150]})
        time.sleep(.2)
    result = {'members':team['members'],'rover_attribute':team['rover_attribute'],'videos':matches[:5],
              'checked_results':len(merged),'ambiguous_candidates':len(pending),'fetch_errors':failures}
    print(json.dumps({'team':team['members'],'confirmed':len(matches),'ambiguous':len(pending),'errors':len(failures)}, ensure_ascii=False),flush=True)
    return team['id'], result


def main():
    teams = json.loads((FOLDER/'disabled_recheck_targets.json').read_text(encoding='utf-8'))
    # The named classic team is reviewed first, followed by every disabled recipe.
    teams.sort(key=lambda t: set(t['members']) != {'绯雪','洛瑟菈','穗穗'})
    results = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for key, result in pool.map(review, teams):
            results[key] = result
    (FOLDER/'disabled_recheck_review.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    verified = {k:v for k,v in results.items() if v['videos']}
    (FOLDER/'browser_recheck_verified.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Reviewed',len(results),'newly supported',len(verified))


if __name__ == '__main__':
    main()
