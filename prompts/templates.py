from utils.data_loader import Schema, Column, Table


def _format_column(col: Column, augmented: bool) -> str:
    parts = [f"{col.name} {col.type}"]
    if augmented and col.alias_vi:
        synonyms = ", ".join([col.alias_vi] + col.synonym[:2])
        parts.append(f"alias: {synonyms}")
    if augmented and col.sample_values:
        parts.append(f"values: {', '.join(col.sample_values)}")
    if augmented and col.description:
        parts.append(f"-- {col.description}")
    return " | ".join(parts)


def _format_schema(schema: Schema, augmented: bool) -> str:
    lines = []
    foreign_keys = []

    for table in schema.tables:
        header = f"Table: {table.name}"
        if augmented and table.alias_vi:
            header += f" ({table.alias_vi})"
        lines.append(header)
        for col in table.columns:
            lines.append(f"  - {_format_column(col, augmented)}")
            if col.foreign_key_to:
                foreign_keys.append(f"{table.name}.{col.name} = {col.foreign_key_to}")
        lines.append("")

    if foreign_keys:
        lines.append("Foreign keys:")
        lines.extend(f"  {fk}" for fk in foreign_keys)

    return "\n".join(lines).strip()


def build_sql_generation_prompt(question: str, schema: Schema, augmented: bool, evidence: str = "") -> str:
    schema_text = _format_schema(schema, augmented=augmented)
    evidence_section = f"\n### Evidence\n{evidence}" if evidence and evidence.strip() else ""
    return f"""### Task
Given a SQLite database schema and a question in Vietnamese, generate the correct SQL query.
Only return the SQL query, no explanation.

### Schema
{schema_text}{evidence_section}

### Question
{question}

### SQL
"""


def build_augmentation_prompt(table_name: str, columns: list[Column], sample_values: dict[str, list[str]]) -> str:
    col_lines = []
    for col in columns:
        vals = sample_values.get(col.name, [])
        val_str = f" (sample: {', '.join(str(v) for v in vals[:3])})" if vals else ""
        col_lines.append(f"  - {col.name} {col.type}{val_str}")
    cols_text = "\n".join(col_lines)

    return f"""You are a bilingual database expert. Given a SQL table schema, generate Vietnamese metadata.

For the table, provide:
- alias_vi: Vietnamese name of the table (short, natural)

For each column, provide:
- alias_vi: Vietnamese name of the column
- synonym: list of 2-3 Vietnamese synonyms
- description: one-sentence Vietnamese description of the column's meaning

Return ONLY a valid JSON object with this exact structure:
{{
  "table_name": "{table_name}",
  "alias_vi": "<Vietnamese table name>",
  "columns": [
    {{
      "name": "<column_name>",
      "alias_vi": "<Vietnamese name>",
      "synonym": ["<syn1>", "<syn2>"],
      "description": "<one sentence description>"
    }}
  ]
}}

Table schema:
{table_name}:
{cols_text}
"""
