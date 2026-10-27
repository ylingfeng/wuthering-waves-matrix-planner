"""Resolve ambiguous short names only when public descriptions/tags name the role."""
import json
import time
from pathlib import Path
import requests
from tools.review_browser_evidence import AMBIGUOUS, clean

ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'reference_analysis/bilibili'
    pending=json.loads((folder/'browser_ambiguous.json').read_text(encoding='utf-8'))
    results=json.loads((folder/'browser_resolved.json').read_text(encoding='utf-8')) if (folder/'browser_resolved.json').exists() else {}
    session=requests.Session()
    session.headers['User-Agent']='matrix-team-research/1.0'
    for key,team in pending.items():
        if key in results:continue
        accepted=[]
        for video in team['videos']:
            p=folder/(video['bvid']+'.json')
            try:
                data=json.loads(p.read_text(encoding='utf-8')).get('data',{}) if p.exists() else {}
                tag_path=folder/(video['bvid']+'.tags.json')
                if tag_path.exists():tags=json.loads(tag_path.read_text(encoding='utf-8'))
                else:
                    r=session.get('https://api.bilibili.com/x/tag/archive/tags',params={'bvid':video['bvid']},timeout=15)
                    if r.status_code!=200:continue
                    payload=r.json()
                    if payload.get('code')!=0:continue
                    tags=[v['tag_name'] for v in payload.get('data',[])]
                    tag_path.write_text(json.dumps(tags,ensure_ascii=False,indent=2),encoding='utf-8')
                text=clean(data.get('title',video['title'])+' '+data.get('desc','')+' '.join(tags))
                ambiguous=[n for n in team['members'] if n in AMBIGUOUS]
                if all(clean(n) in text or n=='莫特斐' and '莫特菲' in text for n in ambiguous):
                    accepted.append({**video,'description':data.get('desc','')+'\n视频标签：'+'、'.join(tags),'resolution':'标题三人简称＋视频标签或简介全名消歧'})
                    break
            except (requests.RequestException,ValueError,KeyError):pass
            time.sleep(.4)
        if accepted:results[key]={**team,'videos':accepted};print(team['members'],'resolved',flush=True)
        else:print(team['members'],'pending',flush=True)
        (folder/'browser_resolved.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
