import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Column:
    name: str
    type: str
    alias_vi: str = ""
    synonym: list[str] = field(default_factory=list)
    sample_values: list[str] = field(default_factory=list)
    description: str = ""
    is_primary_key: bool = False
    foreign_key_to: Optional[str] = None  # "table.column"


@dataclass
class Table:
    name: str
    alias_vi: str = ""
    columns: list[Column] = field(default_factory=list)


@dataclass
class Schema:
    db_id: str
    tables: list[Table] = field(default_factory=list)


@dataclass
class Example:
    question_id: str
    db_id: str
    question: str
    gold_sql: str
    evidence: str = ""  # BIRD only


def load_spider_vi(dev_path: str) -> list[Example]:
    with open(dev_path, encoding="utf-8") as f:
        data = json.load(f)
    examples = []
    for i, item in enumerate(data):
        examples.append(Example(
            question_id=f"spider_dev_{i:04d}",
            db_id=item["db_id"],
            question=item["question"],
            gold_sql=item["query"],
        ))
    return examples


def load_bird_vi(dev_path: str) -> list[Example]:
    with open(dev_path, encoding="utf-8") as f:
        data = json.load(f)
    examples = []
    for item in data:
        examples.append(Example(
            question_id=f"bird_dev_{item['question_id']:04d}",
            db_id=item["db_id"],
            question=item["question"],
            gold_sql=item["SQL"],
            evidence=item.get("evidence", ""),
        ))
    return examples


def load_schema_from_db(db_path: str, db_id: str) -> Schema:
    """Extract schema directly from SQLite database file."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    table_names = [row[0] for row in cursor.fetchall()]

    tables = []
    for table_name in table_names:
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        col_infos = cursor.fetchall()

        cursor.execute(f"PRAGMA foreign_key_list('{table_name}')")
        fk_infos = {row[3]: f"{row[2]}.{row[4]}" for row in cursor.fetchall()}

        columns = []
        for col in col_infos:
            # col: (cid, name, type, notnull, dflt_value, pk)
            col_name = col[1]
            sample_values = _get_sample_values(cursor, table_name, col_name)
            columns.append(Column(
                name=col_name,
                type=col[2] or "TEXT",
                is_primary_key=bool(col[5]),
                foreign_key_to=fk_infos.get(col_name),
                sample_values=sample_values,
            ))
        tables.append(Table(name=table_name, columns=columns))

    conn.close()
    return Schema(db_id=db_id, tables=tables)


def _get_sample_values(cursor: sqlite3.Cursor, table: str, column: str, limit: int = 3) -> list[str]:
    try:
        cursor.execute(
            f"SELECT DISTINCT [{column}] FROM [{table}] WHERE [{column}] IS NOT NULL LIMIT {limit}"
        )
        return [str(row[0]) for row in cursor.fetchall()]
    except Exception:
        return []


def load_augmented_schema(augmented_dir: str, db_id: str) -> Optional[Schema]:
    """Load pre-generated augmented schema JSON if it exists."""
    path = Path(augmented_dir) / f"{db_id}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    tables = []
    for t in data["tables"]:
        columns = [
            Column(
                name=c["name"],
                type=c.get("type", "TEXT"),
                alias_vi=c.get("alias_vi", ""),
                synonym=c.get("synonym", []),
                sample_values=c.get("sample_values", []),
                description=c.get("description", ""),
                is_primary_key=c.get("is_primary_key", False),
                foreign_key_to=c.get("foreign_key_to"),
            )
            for c in t["columns"]
        ]
        tables.append(Table(
            name=t["name"],
            alias_vi=t.get("alias_vi", ""),
            columns=columns,
        ))
    return Schema(db_id=data["db_id"], tables=tables)
