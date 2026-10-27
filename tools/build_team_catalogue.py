"""Build editable-planner seed data from workshop and downloaded Wiki guides."""
import csv
import hashlib
import html
import json
import re
from pathlib import Path

from tools.team_base_scores import default_team_score
from tools.research_matrix_teams import NAMES, OWNED_CANDIDATES

ROOT = Path(__file__).resolve().parents[1]


def main():
    roster = list(csv.DictReader((ROOT / "character.csv").open(encoding="utf-8-sig")))
    names = {r["角色名称"] for r in roster}
    variants = {f"漂泊者·{attr}" for attr in ("衍射", "湮灭", "气动", "导电")}
    token = "(?:" + "|".join(re.escape(n) for n in sorted(names | variants, key=len, reverse=True)) + ")"
    recipe = re.compile(rf"({token})\s*\+\s*({token})\s*\+\s*({token}(?:\s*/\s*{token})*)")
    teams = {}

    def add(members, attribute, evidence, note, source, axes=(), enabled=True, priority=0):
        if len(set(members)) != 3 or not set(members) <= names:
            return
        identity = "|".join(sorted(members)) + "|" + attribute
        key = hashlib.sha256(identity.encode()).hexdigest()[:16]
        if key not in teams:
            teams[key] = {"id": key, "members": list(members), "rover_attribute": attribute,
                          "enabled": enabled, "priority": priority, "note": note,
                          "evidence": evidence, "sources": [], "axes": [], "selected_axis": "", "origin": "catalogue"}
        item = teams[key]
        if source not in item["sources"]:
            item["sources"].append(source)
        item["axes"].extend(a for a in axes if a["id"] not in {x["id"] for x in item["axes"]})
        if not item["selected_axis"] and item["axes"]:
            item["selected_axis"] = item["axes"][0]["id"]
        if priority > item["priority"]:
            item.update(priority=priority, evidence=evidence, note=note)
        return item

    workshop = json.loads((ROOT / "tmp/team_research/workshop_teams.json").read_text(encoding="utf-8"))
    curated = {frozenset(t): t for t in OWNED_CANDIDATES}
    for source in workshop["teams"]:
        members = tuple(NAMES[n] for n in source["members"])
        text = "\n".join(c["description"] for c in source["codes"])
        explicit = any(k in text for k in ("矩阵", "矩陣"))
        farming = not explicit and ("速刷" in text or "刷4C" in text or text.strip() in {"11", "3"})
        members = curated.get(frozenset(members), members)
        attribute = ""
        if "漂泊者" in members:
            attribute = "导电" if "雷主" in text else "衍射" if "光主" in text else "气动" if "卡提希娅" in members else ""
        axes = [{"id": c["filename"], "name": c["name"], "author": c["author"], "version": c["version"],
                 "description": c["description"], "url": c["downloadUrl"]} for c in source["codes"]]
        add(members, attribute, "工坊·明确矩阵" if explicit else "工坊·通用参考",
            "作者说明为刷4C/测试用途，默认不参与" if farming else "具体槽位、起手位和装备要求见所选轴说明；尚未验证本账号配置。",
            source["jsonUrl"], axes, not farming, 3 if explicit else 2)

    def walk(value):
        if isinstance(value, dict):
            if value.get("title") == "主流队友":
                yield value.get("content", "")
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    quotes = []
    for path in sorted((ROOT / "tmp/team_research").glob("entry_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("code") != 200:
            continue
        entry = data["data"]
        url = f"https://wiki.kurobbs.com/mc/item/{entry['id']}"
        for content in set(walk(entry)):
            cells = [re.sub(r"\s+", " ", html.unescape(re.sub("<[^>]*>", " ", cell))).strip()
                     for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", content, re.S)]
            for i, cell in enumerate(cells[:-1]):
                if cell != "队伍组成":
                    continue
                text = cells[i + 1]
                quotes.append({"title": entry["name"], "quote": text, "url": url})
                for match in recipe.finditer(text):
                    for third in re.split(r"\s*/\s*", match[3]):
                        raw = [match[1], match[2], third]
                        attr = next((n.split("·")[-1] for n in raw if n.startswith("漂泊者·")), "")
                        members = ["漂泊者" if n.startswith("漂泊者·") else n for n in raw]
                        add(members, attr, "Wiki·明确配队", f"原文：{match[0]}。通用攻略推荐，矩阵实战待验证。", url, priority=2)
    # Explicitly labelled extrapolations: preserve the source-backed damage pair,
    # replace a generic support using its own guide's all-characters statement.
    supports = {
        "白芷": "https://wiki.kurobbs.com/mc/item/1347344108314509312",
        "穗穗": "https://wiki.kurobbs.com/mc/item/1520510830431072256",
    }
    for original in list(teams.values()):
        if original["evidence"] != "Wiki·明确配队":
            continue
        for slot, member in enumerate(original["members"]):
            if member not in {"守岸人", "维里奈"}:
                continue
            for replacement, source in supports.items():
                members = original["members"].copy()
                members[slot] = replacement
                item = add(members, original["rover_attribute"], "机制推导·待验证",
                           f"保留Wiki推荐输出搭档，将{member}替换为{replacement}；其攻略标注适配所有角色。该三人组合并非原文直接推荐，矩阵效果待测。",
                           source, priority=1)
                if item:
                    for url in original["sources"]:
                        if url not in item["sources"]:
                            item["sources"].append(url)
    dest = ROOT / "config/team_planner"
    dest.mkdir(parents=True, exist_ok=True)
    supplements = dest / "pair_supplements.json"
    if supplements.exists():
        for item in json.loads(supplements.read_text(encoding="utf-8")):
            previous = teams.get(item["id"])
            if previous is None:
                teams[item["id"]] = item
            else:
                previous["sources"] = list(dict.fromkeys(previous["sources"] + item["sources"]))
                if previous["evidence"] == "机制推导·待验证" and item["evidence"] != previous["evidence"]:
                    previous.update(evidence=item["evidence"], note=item["note"], priority=item["priority"])
    researched = dest / "all_character_supplements.json"
    if researched.exists():
        for item in json.loads(researched.read_text(encoding="utf-8")):
            previous = teams.get(item["id"])
            if previous is None:
                teams[item["id"]] = item
            else:
                previous["sources"] = list(dict.fromkeys(previous["sources"] + item["sources"]))
                previous["recommendation_quotes"] = item.get("recommendation_quotes", [])
                if previous["evidence"] == "机制推导·待验证":
                    previous.update(evidence=item["evidence"], note=item["note"])
    audit_path = ROOT / 'reference_analysis/matrix_teams/source_audit_all.json'
    audits = {r['id']: r for r in json.loads(audit_path.read_text(encoding='utf-8'))} if audit_path.exists() else {}
    for team in teams.values():
        audit = audits.get(team['id'])
        if audit:
            team['source_audit'] = {k: audit[k] for k in ('matched', 'video_status', 'issue', 'matrix_confirmed', 'default_status_reason')}
            team['default_enabled'] = team['enabled'] = audit['default_enabled']
        team["priority"] = default_team_score(team)
        team['default_priority'] = team['priority']
    (dest / "catalogue.json").write_text(json.dumps(list(teams.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "reference_analysis/matrix_teams/wiki_quotes.json").write_text(json.dumps(quotes, ensure_ascii=False, indent=2), encoding="utf-8")
    owned = {r["角色名称"] for r in roster if r["可用"] == "是"}
    print(f"候选库 {len(teams)} 队；现有角色可组成 {sum(set(t['members']) <= owned and t['enabled'] for t in teams.values())} 队；保留工坊 {sum(len(t['axes']) for t in teams.values())} 套轴")


if __name__ == "__main__":
    main()
