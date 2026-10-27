"""Read public video metadata and its author-provided collection; cache evidence."""
import argparse
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('bvid')
    args = parser.parse_args()
    response = requests.get('https://api.bilibili.com/x/web-interface/view',
        params={'bvid': args.bvid}, headers={'User-Agent': 'matrix-team-research/1.0'}, timeout=20)
    response.raise_for_status()
    data = response.json()
    if data.get('code') != 0:
        raise RuntimeError(data.get('message', 'Video metadata unavailable'))
    folder = ROOT / 'reference_analysis/bilibili'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f'{args.bvid}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    video = data['data']
    print(video['title'])
    print(video.get('desc', ''))
    for section in video.get('ugc_season', {}).get('sections', []):
        for episode in section.get('episodes', []):
            print(episode['bvid'], episode['title'])


if __name__ == '__main__':
    main()
