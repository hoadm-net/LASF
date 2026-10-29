"""Check that every dev database has an augmented schema and report metadata coverage.

Exits non-zero if a schema file is missing. Writes augmentation/augmented_schemas/_coverage.csv.
"""

import csv
import json
import sys
from pathlib import Path

import yaml

cfg = yaml.safe_load(open("configs/config.yaml"))
aug_dir = Path(cfg["augmentation"]["output_dir"])
rows, missing = [], []
for ds in ("spider_vi", "bird_vi"):
    dbs = sorted({e["db_id"] for e in json.load(open(cfg["data"][ds]["dev"], encoding="utf-8"))})
    for db in dbs:
        path = aug_dir / f"{db}.json"
        if not path.exists():
            missing.append(db)
            continue
        schema = json.load(open(path, encoding="utf-8"))
        cols = [c for t in schema["tables"] for c in t["columns"]]
        rows.append({
            "dataset": ds, "db_id": db, "n_tables": len(schema["tables"]), "n_columns": len(cols),
            "tables_with_alias": sum(bool(t.get("alias_vi")) for t in schema["tables"]),
            "columns_with_alias": sum(bool(c.get("alias_vi")) for c in cols),
            "columns_with_description": sum(bool(c.get("description")) for c in cols),
        })

with open(aug_dir / "_coverage.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

for ds in ("spider_vi", "bird_vi"):
    r = [x for x in rows if x["dataset"] == ds]
    n = sum(x["n_columns"] for x in r)
    print(f"{ds}: {len(r)} DBs, column alias coverage {sum(x['columns_with_alias'] for x in r)}/{n}")
    for x in r:
        if x["columns_with_alias"] < x["n_columns"]:
            print(f"  {x['db_id']}: {x['columns_with_alias']}/{x['n_columns']} columns augmented")
if missing:
    print(f"MISSING augmented schemas: {missing}")
    sys.exit(1)
