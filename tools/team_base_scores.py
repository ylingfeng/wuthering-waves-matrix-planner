"""User-approved default team score tiers; no additional source multiplier."""
from urllib.parse import urlsplit


def default_team_score(team):
    if team.get("base_score_override"):
        return team["base_score_override"]["score"]
    if team.get('source_audit'):
        evidence = team['source_audit'].get('matched', [])
        if any(x['kind'] == 'video' and x.get('matrix') for x in evidence):
            return 2.5
        if any(x['kind'] == 'workshop' and x.get('matrix') for x in evidence):
            return 2
        if any(x['kind'] == 'wiki' for x in evidence):
            return 1.5
        return 1
    return 1
