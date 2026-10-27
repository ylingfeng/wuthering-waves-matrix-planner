"""Materialize static tab entrypoints; no server rewrite or backend required."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_routes(site=ROOT / 'web/team_planner'):
    html = (site / 'index.html').read_text(encoding='utf-8')
    for route in ('characters', 'teams', 'results'):
        folder = site / route
        folder.mkdir(exist_ok=True)
        (folder / 'index.html').write_text(html.replace('<base href="./">', '<base href="../">'), encoding='utf-8')


if __name__ == '__main__':
    build_routes()
