"""Plan distinct three-character teams without changing combat state."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Candidate:
    key: str
    members: tuple[str, str, str]
    priority: float = 0  # Reviewed team score, not a damage estimate.


def read_stamina(path: Path) -> dict[str, int]:
    result = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            name = row["角色名称"].strip()
            override = row["本周变动体力"].strip()
            value = int(override if override else row["基础体力"])
            if not name or name in result or value < 0:
                raise ValueError(f"Invalid character/stamina: {name!r}")
            result[name] = value if row.get("可用", "是") == "是" and row.get("已实装", "是") == "是" else 0
    return result


def optimize(stamina: dict[str, int], candidates: list[Candidate]) -> list[Candidate]:
    """Exact search: maximize distinct teams, then total reviewed priority.

    A character spends one point per selected team. Attribute variants use
    the same character identity/budget. No mandatory healer. Candidate keys
    identify compositions, not axes; multiple axes cannot multiply teams.
    """
    if any(type(v) is not int or v < 0 for v in stamina.values()):
        raise ValueError("Stamina must be a nonnegative integer")
    names = sorted(stamina)
    index = {name: i for i, name in enumerate(names)}
    unique = {}
    for team in candidates:
        if len(team.members) != 3 or len(set(team.members)) != 3:
            raise ValueError(f"Team must contain three distinct characters: {team.key}")
        if any(name not in stamina for name in team.members):
            raise ValueError(f"Unknown character: {team.key}")
        identity = tuple(sorted(team.members))
        previous = unique.get(identity)
        if previous is None or team.priority > previous.priority:
            unique[identity] = team
    teams = sorted(unique.values(), key=lambda t: t.key)
    member_indices = [tuple(index[n] for n in t.members) for t in teams]

    if len(teams) > 20:
        # Exact integer optimization scales to hundreds of candidate teams.
        import numpy as np
        from scipy.optimize import Bounds, LinearConstraint, milp

        incidence = np.zeros((len(names), len(teams)))
        for column, indices in enumerate(member_indices):
            incidence[list(indices), column] = 1
        constraints = [LinearConstraint(incidence, 0, [stamina[n] for n in names])]
        bounds = Bounds(0, 1)
        first = milp(-np.ones(len(teams)), integrality=np.ones(len(teams)),
                     bounds=bounds, constraints=constraints, options={"time_limit": 20, "mip_rel_gap": 0})
        if not first.success:
            raise RuntimeError("配队求解未证明最优，请减少候选后重试")
        count = round(sum(first.x))
        constraints.append(LinearConstraint(np.ones((1, len(teams))), count, count))
        second = milp(-np.array([t.priority for t in teams], dtype=float),
                      integrality=np.ones(len(teams)), bounds=bounds, constraints=constraints,
                      options={"time_limit": 20, "mip_rel_gap": 0})
        if not second.success:
            raise RuntimeError("优先级求解未证明最优，请重试")
        return [t for t, chosen in zip(teams, second.x) if chosen > 0.5]

    @lru_cache(maxsize=None)
    def search(position, remaining):
        if position == len(teams) or sum(remaining) < 3:
            return (0, 0, ())
        best = search(position + 1, remaining)
        indices = member_indices[position]
        if all(remaining[i] > 0 for i in indices):
            after = list(remaining)
            for i in indices:
                after[i] -= 1
            count, score, selected = search(position + 1, tuple(after))
            take = (count + 1, score + teams[position].priority, (position,) + selected)
            if take[:2] > best[:2]:
                best = take
        return best

    _, _, chosen = search(0, tuple(stamina[n] for n in names))
    return [teams[i] for i in chosen]
