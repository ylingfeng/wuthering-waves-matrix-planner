"""Conservative exact three-role matching of cached Bilibili search titles."""
import itertools
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ALIASES = {
 '爱弥斯':['爱','爱弥丝'], '达妮娅':['达','达尼娅'], '千咲':['千'], '守岸人':['守'],
 '维里奈':['维','维利奈'], '白芷':['白'], '卜灵':['卜'], '穗穗':['穗'],
 '琳奈':['琳','林奈'], '清宵':['清','青霄'], '绯雪':['绯'], '西格莉卡':['西'],
 '嘉贝莉娜':['嘉'], '弗洛洛':['弗'], '坎特蕾拉':['坎'], '夏空':['夏'],
 '赞妮':['赞'], '菲比':['菲'], '布兰特':['布'], '椿':['椿'], '相里要':['相'], '长离':['长'],
 '折枝':['折'], '吟霖':['吟'], '忌炎':['忌'], '尤诺':['尤','月'], '鉴心':['鉴'],
 '散华':['散'], '丹瑾':['丹'], '秋水':['秋'], '灯灯':['灯'], '渊武':['渊'],
 '桃祈':['桃'], '釉瑚':['釉'], '炽霞':['炽'], '凌阳':['凌'], '安可':['安'],
 '心':['心'], '今汐':['汐'], '锁暝':['锁','锁冥'], '丽贝卡':['丽'], '景燃':['景'], '陆·赫斯':['陆','陆赫斯'],
 '奥古斯塔':['奥','日'], '仇远':['仇'], '珂莱塔':['珂'],
 '洛瑟菈':['洛瑟拉'], '莫特斐':['莫特菲'],
 # Deliberately exclude ambiguous 卡/莫/洛/露/秧. Expand via metadata before accepting.
}
AMBIGUOUS = {'卡提希娅':'卡','卡卡罗':'卡','莫宁':'莫','莫特斐':'莫','洛可可':'洛','洛瑟菈':'洛',
             '露帕':'露','露西':'露','秧秧':'秧','秧秧·玄翎':'秧'}


def clean(s):
    return re.sub(r'[^\u4e00-\u9fff]', '', s)


def tokens(team, relaxed=False):
    result=[]
    for name in team['members']:
        aliases=[clean(name)]+ALIASES.get(name, [])
        if name=='漂泊者':
            aliases=[{'衍射':'光','湮灭':'暗','气动':'风','导电':'雷'}[team['rover_attribute']]]
            aliases += [aliases[0]+'主', '漂泊者'+team['rover_attribute'], team['rover_attribute']+'漂泊者']
        if relaxed and name in AMBIGUOUS:
            aliases.append(AMBIGUOUS[name])
        result.append(list(set(aliases)))
    return result


def patterns(team, relaxed=False):
    return {' '.join(p).replace(' ', '') for group in itertools.product(*tokens(team, relaxed)) for p in itertools.permutations(group)}


def title_matches(title, patterns):
    # Do not join characters across listed teams, or take the last character
    # of 鉴心 as 心. A short code must occupy a plausible team-name boundary.
    prefixes=('矩阵','模板','试用','配队','鸣潮','队伍','聚爆','同奏队','低配','低金','移动端','新版')
    suffixes=('矩阵','轮椅','循环','批发','手法','教学','标准','进阶','实战','简化','轮切','通用','简单','全','满','无','低','高','轴','队','手机','移动','二金','一金','首次','首轮','五','四','三','双','单','千','万','轻','打','能','最','基础','起手','开','一穿','输出','伤害','乱打')
    for part in re.split(r'[/、，,。！!？?；;|：:\[\]【】()（）]',title):
        normalized=clean(part)
        for pattern in patterns:
            pos=normalized.find(pattern)
            if pos<0:continue
            before,after=normalized[:pos],normalized[pos+len(pattern):]
            if (not before or before.endswith(prefixes)) and (not after or after.startswith(suffixes)):
                return True
    return False


def main():
    teams=json.loads((ROOT/'config/team_planner/teams.json').read_text(encoding='utf-8'))
    verified,ambiguous={},{}
    for team in teams:
        path=ROOT/'reference_analysis/bilibili/browser_search'/f"{team['id']}.json"
        if not path.exists():continue
        record=json.loads(path.read_text(encoding='utf-8'))
        exact=patterns(team);relaxed=patterns(team,True)
        hits=[];pending=[]
        for video in record.get('results',[]):
            title=video['title'];normalized=clean(title)
            if not re.search('矩阵|矩陣',title) or re.search('求.*教|求.*指|求助|不会|没打出',title):continue
            if title_matches(title,exact):hits.append(video)
            elif title_matches(title,relaxed):pending.append(video)
        def rank(v):return (not bool(re.search('教学|手法|攻略|轮椅|轴',v['title'])),v['bvid'])
        hits.sort(key=rank);pending.sort(key=rank)
        if hits:verified[team['id']]={'members':team['members'],'rover_attribute':team['rover_attribute'],'videos':hits[:5]}
        if pending:ambiguous[team['id']]={'members':team['members'],'rover_attribute':team['rover_attribute'],'videos':pending[:3]}
    folder=ROOT/'reference_analysis/bilibili'
    (folder/'browser_verified.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'browser_ambiguous.json').write_text(json.dumps(ambiguous,ensure_ascii=False,indent=2),encoding='utf-8')
    print('标题三人明确匹配',len(verified),'简称需复核',len(ambiguous))


if __name__=='__main__':main()
