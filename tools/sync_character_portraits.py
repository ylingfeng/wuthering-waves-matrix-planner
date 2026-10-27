"""Import the public Kuro Wiki roster/portraits; never mark new entries owned."""
import csv
import io
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / "tmp/team_research/resonators_catalogue.json"
    records = json.loads(source.read_text(encoding="utf-8"))["data"]["results"]["records"]
    portraits = ROOT / "assets/characters"
    portraits.mkdir(parents=True, exist_ok=True)
    path = ROOT / "character.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames)
        rows = list(reader)
    if "可用" not in fields:
        backup = ROOT / "reference_analysis/matrix_teams/character_before_availability.csv"
        if not backup.exists():
            shutil.copy2(path, backup)
        fields.append("可用")
        for row in rows:
            row["可用"] = "是"
    known = {r["角色名称"] for r in rows}
    for field in ("加权", "星级"):
        if field not in fields:
            fields.append(field)
    manifest = {}
    for record in records:
        original = record["name"].strip()
        name = "漂泊者" if original.startswith("漂泊者-") else original
        if name not in known:
            rows.append({"角色名称": name, "奶妈标注": "", "基础体力": "1",
                         "本周变动体力": "", "可选属性": "", "可用": "",
                         "星级": record["content"].get("star", ""),
                         "加权": "1.1" if str(record["content"].get("star")) == "5" else "1",
                         **({"已实装": ""} if "已实装" in fields else {})})
            known.add(name)
        if name not in manifest:
            manifest[name] = {"file": f"{name}.png", "source": record["content"]["contentUrl"],
                              "wiki": f"https://wiki.kurobbs.com/mc/item/{record['entryId']}"}

    def download(item):
        name, info = item
        target = portraits / info["file"]
        if not target.exists():
            with urlopen(info["source"], timeout=30) as response:
                image = Image.open(io.BytesIO(response.read())).convert("RGBA")
            image.thumbnail((360, 480))
            image.save(target, format="PNG")
        with Image.open(target) as image:
            image.verify()
        return name

    with ThreadPoolExecutor(max_workers=6) as pool:
        downloaded = list(pool.map(download, manifest.items()))
    (portraits / "sources.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"角色 {len(rows)}；可用 {sum(r['可用'] == '是' for r in rows)}；PNG头像 {len(downloaded)}")


if __name__ == "__main__":
    main()
