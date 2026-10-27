"""Refresh public workshop metadata and generate a reproducible team plan.

Usage: python -m tools.research_matrix_teams [--refresh]
Does not import or execute workshop code, or consume game stamina.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from matrix_planner.team_planning import Candidate, optimize, read_stamina

ROOT = Path(__file__).resolve().parents[1]
URL = "https://okwwcharcode.ok-script.com/teams.json"
SNAPSHOT = ROOT / "tmp/team_research/workshop_teams.json"
OUT = ROOT / "reference_analysis/matrix_teams"
NAMES = {
    "Aemeath": "爱弥斯", "Augusta": "奥古斯塔", "Baizhi": "白芷",
    "Brant": "布兰特", "Buling": "卜灵", "Calcharo": "卡卡罗",
    "Camellya": "椿", "Cantarella": "坎特蕾拉", "Carlotta": "珂莱塔",
    "Cartethyia": "卡提希娅", "Changli": "长离", "Chisa": "千咲",
    "Chixia": "炽霞", "Ciaccona": "夏空", "Denia": "达妮娅",
    "Galbrena": "嘉贝莉娜", "Hiyuki": "绯雪", "Hsin": "心",
    "Iuno": "尤诺", "JingRan": "景燃", "Jinhsi": "今汐", "Jiyan": "忌炎",
    "Lucilla": "洛瑟菈", "Lucy": "露西", "Lupa": "露帕", "Lynae": "琳奈",
    "Mornye": "莫宁", "Mortefi": "莫特斐", "Phoebe": "菲比",
    "Phrolova": "弗洛洛", "Qingxiao": "清宵", "Qiuyuan": "仇远",
    "Rebecca": "丽贝卡", "Rover": "漂泊者", "Sanhua": "散华",
    "Shorekeeper": "守岸人", "Sigrika": "西格莉卡", "Suisui": "穗穗",
    "Verina": "维里奈", "Yangyang: Xuanling": "秧秧·玄翎",
    "Youhu": "釉瑚", "Zani": "赞妮", "Zhezhi": "折枝",
}
# Composition order is for display, NOT a declaration of every axis's slots.
# Each axis retains its original slot/start/gear requirements in its description.
OWNED_CANDIDATES = [
    ("爱弥斯", "达妮娅", "千咲"), ("爱弥斯", "琳奈", "莫宁"),
    ("心", "漂泊者", "卜灵"), ("心", "卜灵", "穗穗"),
    ("今汐", "长离", "维里奈"), ("绯雪", "洛瑟菈", "千咲"),
    ("秧秧·玄翎", "千咲", "穗穗"), ("清宵", "达妮娅", "莫宁"),
    ("绯雪", "洛瑟菈", "穗穗"), ("绯雪", "洛瑟菈", "维里奈"),
    ("绯雪", "琳奈", "穗穗"), ("心", "今汐", "守岸人"),
    ("心", "漂泊者", "穗穗"), ("秧秧·玄翎", "莫特斐", "穗穗"),
]


def write_csv(name, fields, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if args.refresh or not SNAPSHOT.exists():
        with urlopen(URL, timeout=30) as response:
            payload = response.read()
        data = json.loads(payload)
        if not isinstance(data.get("teams"), list):
            raise ValueError("Unexpected workshop response")
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_bytes(payload)
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    stamina = read_stamina(ROOT / "character.csv")
    with (ROOT / "character.csv").open(encoding="utf-8-sig", newline="") as stream:
        owned_names = {r["角色名称"] for r in csv.DictReader(stream) if r.get("可用", "是") == "是"}
    OUT.mkdir(parents=True, exist_ok=True)
    by_members = {}
    details, compositions, candidates = [], [], []
    curated = {frozenset(t): t for t in OWNED_CANDIDATES}
    for source in data["teams"]:
        members = tuple(NAMES.get(n, n) for n in source["members"])
        identity = frozenset(members)
        if len(identity) != 3 or identity in by_members:
            raise ValueError(f"Invalid/duplicate workshop team: {members}")
        by_members[identity] = source
        display = curated.get(identity, members)
        name = "_".join(display)
        missing = [m for m in members if m not in owned_names]
        explicit = any(any(k in c["description"].lower() for k in ("矩阵", "矩陣", "matrix"))
                       for c in source["codes"])
        status = "缺角色" if missing else "暂不纳入：仅刷4C方案" if identity not in curated else "候选"
        evidence = "作者说明明确提及矩阵" if explicit else "已有自定义轴实测" if set(members) == {"爱弥斯", "千咲", "达妮娅"} else "工坊通用轴，矩阵待验证"
        compositions.append({"队伍": name, "轴数量": len(source["codes"]), "状态": status,
                             "缺少角色": "|".join(missing), "矩阵依据": evidence, "来源": source["jsonUrl"]})
        for code in source["codes"]:
            details.append({"队伍": name, "轴名称": code["name"], "作者": code["author"],
                            "版本": code["version"], "说明": code["description"],
                            "更新时间": code["modifiedAt"], "来源": source["jsonUrl"],
                            "代码链接": code["downloadUrl"]})
        if status == "候选":
            candidates.append({"队伍": name, "角色1": display[0], "角色2": display[1], "角色3": display[2],
                               "漂泊者属性": "导电" if "漂泊者" in members else "",
                               "轴数量": len(source["codes"]), "矩阵依据": evidence,
                               "优先分": 0, "来源": source["jsonUrl"]})
    write_csv("workshop_compositions.csv", ["队伍", "轴数量", "状态", "缺少角色", "矩阵依据", "来源"], compositions)
    write_csv("workshop_axes.csv", ["队伍", "轴名称", "作者", "版本", "说明", "更新时间", "来源", "代码链接"], details)
    write_csv("candidates.csv", ["队伍", "角色1", "角色2", "角色3", "漂泊者属性", "轴数量", "矩阵依据", "优先分", "来源"], candidates)
    usable = [Candidate(r["队伍"], tuple(r[f"角色{i}"] for i in (1, 2, 3)), r["优先分"]) for r in candidates]
    selected = optimize(stamina, usable)
    used = Counter(n for t in selected for n in t.members)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "source": URL,
        "workshop_compositions": len(compositions), "workshop_axes": len(details),
        "owned_compositions": sum(not r["缺少角色"] for r in compositions),
        "candidate_compositions": len(candidates), "stamina_total": sum(stamina.values()),
        "unrestricted_upper_bound": sum(stamina.values()) // 3,
        "optimal_count_within_candidates": len(selected),
        "selected": [{"team": t.key, "members": list(t.members),
                      "rover_attribute": "导电" if "漂泊者" in t.members else None} for t in selected],
        "remaining_stamina": {n: v - used[n] for n, v in stamina.items()},
        "limitations": "仅在已收录候选集合内最大化不同配队数量；未评估账号练度、武器、共鸣链或实战伤害。优先分暂为0；不是全游戏最佳阵容。",
    }
    (OUT / "plan.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 矩阵配队候选统计", "", f"来源：{URL}；生成时间：{summary['generated_at']}。", "",
             f"在线工坊：{len(compositions)} 种成员组合，{len(details)} 个输出轴条目。现有名单能组成 {summary['owned_compositions']} 种，其中 1 种仅说明适用高链绯雪刷 4C，暂不纳入矩阵候选。", "",
             "本次只读取公开目录及作者说明，未运行工坊代码。作者声称跑通不等于本账号已验证。奶妈/体力遵照 character.csv，不采用工坊脚本内部的奶妈标志。", "",
             "## 候选组合", "", "| 队伍 | 轴数 | 矩阵依据 |", "| --- | ---: | --- |"]
    lines += [f"| {r['队伍']} | {r['轴数量']} | {r['矩阵依据']} |" for r in candidates]
    lines += ["", "## 体力分配", "",
              f"本周合计 {sum(stamina.values())} 点体力，无组合限制的数量上限为 {sum(stamina.values()) // 3} 队。在本次 {len(candidates)} 种候选中，精确求解最多组成 **{len(selected)} 支不同队伍**。以下是其中一个最优解：", ""]
    lines += [f"- {t.key}" + ("（漂泊者选导电）" if "漂泊者" in t.members else "") for t in selected]
    lines += ["", "## 算法规则", "",
              "每个候选队伍是一个0/1变量；每名角色在所选队伍中的出现次数不得超过本周有效体力。有效体力取本周变动体力，留空则取基础体力。先最大化队伍数，再最大化人工审核的优先分；当前全部优先分为0，不虚构伤害评分。", "",
              "每队必须三名不同角色，不强制奶妈。不同槽位排列、不同输出轴不增加独立组合数。漂泊者四属性共用一个体力池；本次心队的工坊说明指定导电。当前按不同组合各选一次；若以后允许重复同一队，应改为整数次数变量。", "",
              "精确搜索适用于当前14种候选；候选扩展到数百种时改用整数规划求解器，保留同一约束与目标。扩充组合库才能提高当前的6队结果，不应为了凑14队把无依据的三人组合当成合适队伍。", "",
              "角色1/2/3列只是候选展示顺序，实际战斗槽位和起手位必须跟随所选轴说明。完整60条作者说明、共鸣效率、武器和链数要求见 workshop_axes.csv。", "",
              "## 文件与复现", "",
              "- workshop_compositions.csv：完整成员组合，含缺少角色与排除原因。",
              "- workshop_axes.csv：全部方案及原始作者说明、版本、代码链接。",
              "- candidates.csv：当前拥有角色可组成的矩阵候选。",
              "- plan.json：当前候选最大组队结果与每人剩余体力。",
              "- 运行 `python -m tools.research_matrix_teams` 重算；加 `--refresh` 更新在线目录。该命令重建生成文件。",
              "- 本工具仅规划，不扣除 character.csv 体力、不执行配队、不改动已有战斗轴。", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
