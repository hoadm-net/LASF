"""
Zero-shot LLM table selection baseline (in the spirit of C3 / CHESS table selection).

An instruction-tuned LLM reads the full (plain) schema and the question and returns the
relevant tables; all columns of the selected tables are kept. Selections do not depend on
the SQL generator, so they are computed once per dataset by scripts/llm_table_selection.py
and read back from a cache here.
"""

import json
import re
from pathlib import Path

from utils.data_loader import Schema, Table
from prompts.templates import _format_schema


def build_table_selection_prompt(question: str, schema: Schema, evidence: str = "") -> str:
    schema_text = _format_schema(schema, augmented=False)
    evidence_section = f"\n### Evidence\n{evidence}" if evidence and evidence.strip() else ""
    return f"""### Task
Given a SQLite database schema and a question in Vietnamese, list the tables needed to write the SQL query
that answers the question. Include every table needed for joins. Return ONLY a JSON object of the form
{{"tables": ["<table_name>", ...]}}.

### Schema
{schema_text}{evidence_section}

### Question
{question}

### Answer
"""


def parse_tables(text: str, schema: Schema) -> list[str]:
    """Table names from the model output, matched case-insensitively against the schema."""
    names = {t.name.lower(): t.name for t in schema.tables}
    found = []
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            found = json.loads(match.group()).get("tables", [])
        except (json.JSONDecodeError, AttributeError):
            found = []
    if not found:  # fall back to any table name mentioned in the output
        found = [n for n in names if re.search(rf"\b{re.escape(n)}\b", text.lower())]
    out = []
    for n in found:
        key = str(n).strip("`\"' ").lower()
        if key in names and names[key] not in out:
            out.append(names[key])
    return out


class LLMTableSelector:
    def __init__(self, cache_path: str):
        self.selection: dict[tuple[str, str], list[str]] = {}
        with open(cache_path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                self.selection[(r["db_id"], r["question"])] = r["tables"]

    def retrieve(self, question: str, schema: Schema, top_k: int | None = None) -> Schema:
        tables = self.selection.get((schema.db_id, question))
        if tables is None:
            raise KeyError(f"No cached table selection for {schema.db_id}: {question[:60]}")
        if not tables:  # empty or unparsable selection: keep the full schema
            return schema
        keep = set(tables)
        return Schema(db_id=schema.db_id, tables=[Table(t.name, t.alias_vi, list(t.columns))
                                                  for t in schema.tables if t.name in keep])
