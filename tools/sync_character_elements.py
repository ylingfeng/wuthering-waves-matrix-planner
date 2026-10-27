"""Sync immutable elements from a saved official Kuro Wiki roster response."""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ELEMENTS = {'2': '气动', '3': '导电', '4': '冷凝', '5': '热熔', '6': '衍射', '7': '湮灭'}


def sync(catalogue, root=ROOT):
    records = json.loads(Path(catalogue).read_text(encoding='utf-8'))['data']['results']['records']
    by_name = {record['name']: record for record in records}
    roster_path = root / 'character.csv'
    with roster_path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        fields, rows = list(reader.fieldnames), list(reader)
    if '属性' not in fields:
        fields.insert(fields.index('可选属性'), '属性')
    sources = {}
    for row in rows:
        name = row['角色名称']
        if name == '漂泊者':
            # Keep the supported forms and their order; all share one stamina pool.
            row['属性'] = ''
            records_for_rover = [record for record in records if record['name'].startswith('漂泊者-')]
            variants = {}
            for record in records_for_rover:
                element = ELEMENTS[str(record['content']['skillAttr'])]
                variants.setdefault(element, {'element': element, 'url': f"https://wiki.kurobbs.com/mc/item/{record['entryId']}"})
            assert set(row['可选属性'].split('|')) <= variants.keys(), '漂泊者属性来源不完整'
            sources[name] = {'elements': [variants[e] for e in row['可选属性'].split('|')]}
        else:
            record = by_name[name]
            element = ELEMENTS[str(record['content']['skillAttr'])]
            row['属性'], row['可选属性'] = element, ''
            sources[name] = {'element': element, 'url': f"https://wiki.kurobbs.com/mc/item/{record['entryId']}"}
    # Validate everything before writing. No personal configuration or teams are touched.
    seed_path = root / 'web/team_planner/seed.js'
    seed = json.loads(seed_path.read_text(encoding='utf-8').removeprefix('const PLANNER_SEED=').strip().removesuffix(';'))
    elements = {row['角色名称']: row['属性'] for row in rows}
    assert {c['name'] for c in seed['characters']} == elements.keys(), 'CSV 与默认角色名单不一致'
    for character in seed['characters']:
        character['element'] = elements[character['name']]
    with roster_path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    seed_path.write_text('const PLANNER_SEED=' + json.dumps(seed, ensure_ascii=False) + ';\n', encoding='utf-8')
    (root / 'config/team_planner/element_sources.json').write_text(
        json.dumps({'source': '库街区官方 Wiki 共鸣者目录', 'skill_attr': ELEMENTS, 'characters': sources}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'已同步 {len(rows) - 1} 名固定属性角色及漂泊者的可选属性；未修改个人配置。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalogue', type=Path, default=ROOT / 'tmp/team_research/resonators_catalogue.json')
    args = parser.parse_args()
    sync(args.catalogue)


if __name__ == '__main__':
    main()
