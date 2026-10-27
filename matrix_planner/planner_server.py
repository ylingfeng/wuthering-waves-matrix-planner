"""Local HTTP editor for the roster and candidate teams. No game input."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
import math
import itertools
import mimetypes
import os
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from matrix_planner.team_planning import Candidate, optimize

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger("team_planner")

RELEASE_VERSIONS = [f"V1.{i}" for i in range(5)] + [f"V2.{i}" for i in range(9)] + [f"V3.{i}" for i in range(8)]


def source_multiplier(team):
    return 1.0  # Source quality is now represented only by the editable team base score.


def recency_multiplier(character):
    """Small bonus for dedicated main DPS only; unknown releases get none."""
    version = character.get("release_version", "")
    if (not character.get("released", True) or character.get("healer")
            or character.get("roles") != ["主C"] or version not in RELEASE_VERSIONS):
        return 1.0
    return round(1 + RELEASE_VERSIONS.index(version) * 0.002, 6)


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="")
    os.replace(temporary, path)


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.roster_path = self.root / "character.csv"
        self.directory = self.root / "config/team_planner"
        self.teams_path = self.directory / "teams.json"
        self.lock = threading.RLock()
        self.directory.mkdir(parents=True, exist_ok=True)
        if not self.teams_path.exists():
            seed = self.directory / "catalogue.json"
            atomic_write(self.teams_path, seed.read_text(encoding="utf-8") if seed.exists() else "[]")

    def revision(self):
        return hashlib.sha256(self.roster_path.read_bytes() + self.teams_path.read_bytes()).hexdigest()

    def state(self):
        with self.lock:
            with self.roster_path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            characters = [{"name": r["角色名称"], "healer": r["奶妈标注"] == "是",
                           "available": r.get("可用", "是") == "是", "base": int(r["基础体力"]),
                           "weekly": int(r["本周变动体力"]) if r["本周变动体力"] else None,
                           "weight": float(r.get("加权") or 1),
                           "chain": int(r.get("链度") or 0),
                           "rarity": int(r.get("星级") or 0),
                           "roles": (r.get("定位") or ("奶妈" if r["奶妈标注"] == "是" else "待确认")).split("|"),
                           "released": r.get("已实装", "是") == "是",
                           "release_date": r.get("登场时间", ""),
                           "release_version": r.get("实装版本", ""),
                           "element": r.get("属性", ""),
                           "attributes": r["可选属性"].split("|") if r["可选属性"] else [],
                           "avatar": "/portraits/" + quote(r["角色名称"]) + ".png"} for r in rows]
            return {"characters": characters, "teams": json.loads(self.teams_path.read_text(encoding="utf-8")),
                    "revision": self.revision()}

    def save(self, data):
        with self.lock:
            state = self.state()
            if data.get("revision") != state["revision"]:
                raise FileExistsError("数据已被其他页面修改，请刷新后再编辑")
            characters = data.get("characters")
            if not isinstance(characters, list) or len(characters) != len(state["characters"]):
                raise ValueError("角色名单不完整")
            originals = {c["name"]: c for c in state["characters"]}
            names = [c.get("name") for c in characters]
            if len(set(names)) != len(names) or set(names) != set(originals):
                raise ValueError("请通过可用开关调整角色，不要删除或更改角色名称")
            for c in characters:
                if type(c.get("available")) is not bool or type(c.get("healer")) is not bool:
                    raise ValueError("角色可用/奶妈标注必须是布尔值")
                for field in ("base", "weekly"):
                    value = c.get(field)
                    if field == "weekly" and value is None:
                        continue
                    if type(value) is not int or not 0 <= value <= 99:
                        raise ValueError(f"{c['name']}的体力须为0到99的整数，本周体力可留空")
                if type(c.get("weight")) not in (int, float) or not math.isfinite(c["weight"]) or not 1 <= c["weight"] <= 100:
                    raise ValueError("角色加权须为1到100的数字，可使用小数")
                c.setdefault("chain", originals[c["name"]]["chain"])
                if type(c["chain"]) is not int or not 0 <= c["chain"] <= 6:
                    raise ValueError("链度须为0到6的整数")
                roles = c.get("roles", originals[c["name"]]["roles"])
                if not isinstance(roles, list) or not roles or not set(roles) <= {"主C", "辅助", "奶妈", "待确认"}:
                    raise ValueError("角色定位无效")
                c["roles"] = list(dict.fromkeys(roles + ["奶妈"])) if c["healer"] else [r for r in roles if r != "奶妈"] or ["待确认"]
                if len(c["roles"]) > 1 and "待确认" in c["roles"]:
                    c["roles"].remove("待确认")
            teams = data.get("teams")
            if not isinstance(teams, list) or len(teams) > 2000:
                raise ValueError("候选队伍数量无效")
            ids, identities = set(), set()
            for t in teams:
                if not isinstance(t.get("id"), str) or not 1 <= len(t["id"]) <= 180 or t["id"] in ids:
                    raise ValueError("队伍ID重复或无效")
                ids.add(t["id"])
                members = t.get("members", [])
                if len(members) != 3 or len(set(members)) != 3 or not set(members) <= set(originals):
                    raise ValueError("每队请选择三名不同角色")
                attr = t.get("rover_attribute", "")
                if "漂泊者" in members and attr not in originals["漂泊者"]["attributes"]:
                    raise ValueError("包含漂泊者的队伍必须选择属性")
                if "漂泊者" not in members and attr:
                    raise ValueError("不含漂泊者的队伍不能设置漂泊者属性")
                identity = (tuple(sorted(members)), attr)
                if identity in identities:
                    raise ValueError("已有相同角色和属性的队伍，请在原队伍下添加输出轴")
                identities.add(identity)
                if type(t.get("priority")) not in (int, float) or not math.isfinite(t["priority"]) or not 0 <= t["priority"] <= 100:
                    raise ValueError("队伍自身权重须为0到100的数字")
                if type(t.get("enabled")) is not bool or type(t.get("locked", False)) is not bool:
                    raise ValueError("队伍开关无效")
                axes = t.get("axes", [])
                if not isinstance(axes, list) or len(axes) > 100:
                    raise ValueError("输出轴数量无效")
                axis_ids = [a.get("id") for a in axes]
                if any(not isinstance(v, str) or not v for v in axis_ids) or len(set(axis_ids)) != len(axis_ids):
                    raise ValueError("输出轴ID重复或无效")
                if t.get("selected_axis", "") and t["selected_axis"] not in axis_ids:
                    raise ValueError("所选输出轴不存在")
                if any(not isinstance(a.get("name"), str) or not isinstance(a.get("description"), str) for a in axes):
                    raise ValueError("输出轴名称和说明无效")
            stream = io.StringIO(newline="")
            writer = csv.writer(stream)
            writer.writerow(["角色名称", "奶妈标注", "基础体力", "本周变动体力", "属性", "可选属性", "可用", "加权", "星级", "定位", "已实装", "登场时间", "实装版本", "链度"])
            for c in characters:
                writer.writerow([c["name"], "是" if c["healer"] else "", c["base"],
                                 "" if c["weekly"] is None else c["weekly"],
                                 originals[c["name"]]["element"],
                                 "|".join(originals[c["name"]]["attributes"]), "是" if c["available"] else "", c["weight"], originals[c["name"]]["rarity"] or "", "|".join(c["roles"]), "是" if originals[c["name"]]["released"] else "",
                                 originals[c["name"]]["release_date"], originals[c["name"]]["release_version"], c["chain"]])
            previous_roster = self.roster_path.read_text(encoding="utf-8")
            previous_teams = self.teams_path.read_text(encoding="utf-8")
            atomic_write(self.directory / "character.previous.csv", previous_roster)
            atomic_write(self.directory / "teams.previous.json", previous_teams)
            try:
                atomic_write(self.roster_path, "\ufeff" + stream.getvalue())
                atomic_write(self.teams_path, json.dumps(teams, ensure_ascii=False, indent=2))
            except OSError:
                atomic_write(self.roster_path, previous_roster)
                atomic_write(self.teams_path, previous_teams)
                raise
            LOG.info("保存角色%d位、候选队伍%d队", len(characters), len(teams))
            return self.state()

    def plan(self, include_inferred=False, fill_roles=True, all_characters=False):
        with self.lock:
            state = self.state()
        budget = {c["name"]: (c["weekly"] if c["weekly"] is not None else c["base"]) if c["released"] and (c["available"] or all_characters) else 0
                  for c in state["characters"]}
        fixed, options = [], []
        for t in state["teams"]:
            if not t["enabled"]:
                if t.get("locked"):
                    raise ValueError("必选队伍被禁用：" + "_".join(t["members"]))
                continue
            if t.get("locked"):
                fixed.append(t)
            elif all(budget[n] > 0 for n in t["members"]) and (include_inferred or t["evidence"] != "机制推导·待验证"):
                options.append(t)
        spent = Counter(n for t in fixed for n in t["members"])
        excess = [n for n, amount in spent.items() if amount > budget[n]]
        if excess:
            raise ValueError("必选队伍体力不足、角色不可用或未实装：" + "、".join(excess))
        # A different attribute/axis of an already pinned composition isn't a new composition.
        fixed_compositions = {frozenset(t["members"]) for t in fixed}
        if len(fixed_compositions) != len(fixed):
            raise ValueError("必选队伍的角色组合重复，请只保留一种属性方案")
        options = [t for t in options if frozenset(t["members"]) not in fixed_compositions]
        remaining = {n: value - spent[n] for n, value in budget.items()}
        weights = {c["name"]: 1 if all_characters and not c["available"] else c["weight"]
                   for c in state["characters"]}
        weights = {c["name"]: round(weights[c["name"]] * recency_multiplier(c)
                                   * (1 if all_characters and not c["available"] else c["chain"] + 1), 6)
                   for c in state["characters"]}
        # Lexicographic: team count, then sum(team weight * character weights).
        chosen = optimize(remaining, [Candidate(t["id"], tuple(t["members"]),
                          math.prod(weights[n] for n in t["members"]) * t["priority"] * source_multiplier(t))
                          for t in options])
        ids = {t.key for t in chosen}
        selected = fixed + [t for t in options if t["id"] in ids]
        recommended_count = len(selected)
        if fill_roles:
            used_first = Counter(n for t in selected for n in t["members"])
            leftover = {n: value - used_first[n] for n, value in budget.items()}
            roles = {c["name"]: c["roles"]
                     for c in state["characters"]}
            slots = [[n for n in leftover if leftover[n] > 0 and role in roles[n]] for role in ("主C", "辅助", "奶妈")]
            known_sets = {frozenset(t["members"]) for t in selected}
            # Respect manually disabled compositions, even when filling by role.
            excluded = {frozenset(t["members"]) for t in state["teams"] if not t["enabled"]}
            fill = {}
            for trio in itertools.product(*slots):
                identity = frozenset(trio)
                if len(identity) != 3 or identity in known_sets or identity in excluded:
                    continue
                key = "fill-" + hashlib.sha256("|".join(sorted(trio)).encode()).hexdigest()[:16]
                if key in fill:
                    continue
                attribute = ""
                if "漂泊者" in trio:
                    attribute = "湮灭" if trio[0] == "漂泊者" else "导电"
                fill[key] = {"id": key, "members": list(trio), "rover_attribute": attribute,
                             "enabled": True, "priority": 1, "note": "按主C、辅助、奶妈位置用剩余体力补队，未验证技能配合与矩阵表现。",
                             "evidence": "主辅奶·兜底", "sources": [], "axes": [], "selected_axis": "",
                             "origin": "role_fallback", "assigned_roles": ["主C", "辅助", "奶妈"]}
            extra = optimize(leftover, [Candidate(t["id"], tuple(t["members"]),
                             t["priority"] * source_multiplier(t) * math.prod(weights[n] for n in t["members"])) for t in fill.values()])
            selected.extend(fill[t.key] for t in extra)
        for t in selected:
            t["character_weights"] = [weights[n] for n in t["members"]]
            t["unowned_members"] = [n for n in t["members"] if not next(c["available"] for c in state["characters"] if c["name"] == n)]
            t["weight_product"] = math.prod(weights[n] for n in t["members"])
            t["source_multiplier"] = source_multiplier(t)
            t["team_score"] = round(t["priority"] * t["source_multiplier"] * t["weight_product"], 6)
        selected.sort(key=lambda t: (t["team_score"], t["id"]))
        used = Counter(n for t in selected for n in t["members"])
        result = {"selected": selected, "count": len(selected), "eligible": len(options) + len(fixed),
                  "total_stamina": sum(budget.values()), "upper_bound": sum(budget.values()) // 3,
                  "total_weight": sum(t["weight_product"] for t in selected),
                  "total_score": round(sum(t["team_score"] for t in selected), 6),
                  "recommended_count": recommended_count, "fallback_count": len(selected) - recommended_count,
                  "fill_roles": fill_roles,
                  "all_characters": all_characters, "planning_weights": weights,
                  "used": dict(used), "remaining": {n: value - used[n] for n, value in budget.items()},
                  "revision": state["revision"], "include_inferred": include_inferred}
        with self.lock:
            if state["revision"] != self.revision():
                raise FileExistsError("计算期间配置已改变，请重新计算")
            atomic_write(self.directory / "last_plan.json", json.dumps(result, ensure_ascii=False, indent=2))
        LOG.info("求解完成：%d种可用候选，最多%d队", result["eligible"], result["count"])
        return result


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        LOG.info(format, *args)

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path == "/api/state":
            return self.send_json(self.server.store.state())
        if path in {"/", "/index.html"}:
            file = ROOT / "web/team_planner/index.html"
        elif path in {"/app.js", "/style.css", "/seed.js", "/local-planner.js", "/solver-source.js", "/vendor/solver.js"}:
            file = ROOT / "web/team_planner" / path[1:]
        elif path.startswith("/portraits/"):
            file = (self.server.store.root / "assets/characters" / path.removeprefix("/portraits/")).resolve()
            if file.parent != (self.server.store.root / "assets/characters").resolve() or file.suffix != ".png":
                return self.send_error(404)
        else:
            return self.send_error(404)
        if not file.is_file():
            return self.send_error(404)
        body = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", (mimetypes.guess_type(file.name)[0] or "application/octet-stream") + ("; charset=utf-8" if file.suffix != ".png" else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            origin = self.headers.get("Origin")
            if origin and urlsplit(origin).netloc != self.headers.get("Host"):
                return self.send_json({"error": "只接受本地面板的修改请求"}, 403)
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                raise ValueError("需要JSON请求")
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length < 8_000_000:
                raise ValueError("请求大小无效")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("请求必须为对象")
            if self.path == "/api/save":
                return self.send_json(self.server.store.save(data))
            if self.path == "/api/optimize":
                return self.send_json(self.server.store.plan(data.get("include_inferred") is True,
                                      data.get("fill_roles", True) is True, data.get("all_characters") is True))
            return self.send_error(404)
        except FileExistsError as exc:
            self.send_json({"error": str(exc)}, 409)
        except (ValueError, TypeError, KeyError) as exc:
            self.send_json({"error": str(exc)}, 400)
        except Exception:
            LOG.exception("请求失败")
            self.send_json({"error": "操作失败，请查看终端日志"}, 500)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.store = Store(ROOT)
    LOG.info("矩阵配队面板 http://127.0.0.1:%d", args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
