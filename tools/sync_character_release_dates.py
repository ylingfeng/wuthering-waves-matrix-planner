"""Sync verified debut dates to defaults; preserve all personal configuration."""
import argparse
import csv
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sync(source_path, root=ROOT):
    source = json.loads(Path(source_path).read_text(encoding='utf-8'))
    dates = source['characters']
    for name, record in dates.items():
        date.fromisoformat(record['release_date'])
        if not record.get('url') or not record.get('quote'):
            raise ValueError(f'{name}: 缺少日期来源')
    csv_path = root / 'character.csv'
    with csv_path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    seed_path = root / 'web/team_planner/seed.js'
    seed = json.loads(seed_path.read_text(encoding='utf-8').removeprefix('const PLANNER_SEED=').strip().removesuffix(';'))
    by_name = {c['name']:c for c in seed['characters']}
    if not dates.keys() <= by_name.keys():
        raise ValueError('日期资料包含未知角色')
    for row in rows:
        name = row['角色名称']
        if name in dates:
            record = dates[name]
            if row['实装版本'] != record['release_version']:
                raise ValueError(f'{name}: 日期资料与角色版本不一致')
            row['登场时间'] = record['release_date']
            by_name[name]['release_date'] = record['release_date']
    with csv_path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    seed_path.write_text('const PLANNER_SEED=' + json.dumps(seed, ensure_ascii=False) + ';\n', encoding='utf-8')
    print(f'已同步 {len(dates)} 名角色实装日期；个人配置未修改。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'config/team_planner/release_sources.json')
    args = parser.parse_args()
    sync(args.source)


if __name__ == '__main__':
    main()
