import json
import re
import time
import zlib
from pathlib import Path

from transformers import AutoTokenizer, AutoModelForCausalLM, set_seed
import torch

from utils.data_loader import Schema, Column, Table
from prompts.templates import build_augmentation_prompt


class SchemaAugmentor:
    def __init__(self, model_name: str = "Qwen/Qwen2.5-7B-Instruct", device: str = "cpu", max_retries: int = 3,
                 seed: int = 2026, max_new_tokens: int = 1024):
        self.device = device
        self.max_retries = max_retries
        self.seed = seed
        self.max_new_tokens = max_new_tokens
        self.table_stats: list[dict] = []  # one entry per augmented table, reset by augment_schema
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map=device,
        )

    def _generate(self, prompt: str, temperature: float = 0.1) -> tuple[str, int, int]:
        """Returns (text, prompt_tokens, output_tokens)."""
        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
            )
        n_in = inputs["input_ids"].shape[1]
        new_tokens = outputs[0][n_in:]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True), n_in, len(new_tokens)

    def _extract_json(self, text: str) -> dict | None:
        # Extract JSON block from model output
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None

    def augment_table(self, table: Table, db_id: str = "", temperature: float = 0.1) -> Table:
        """Augment a single table with Vietnamese metadata."""
        sample_values = {col.name: col.sample_values for col in table.columns}
        prompt = build_augmentation_prompt(table.name, table.columns, sample_values)
        # Per-table seed: output does not depend on the order in which tables/DBs are processed
        table_seed = self.seed + zlib.crc32(f"{db_id}/{table.name}".encode()) % (2**31)
        stats = {"db_id": db_id, "table": table.name, "n_columns": len(table.columns),
                 "attempts": 0, "ok": False, "prompt_tokens": 0, "output_tokens": 0}
        start = time.perf_counter()

        data = None
        for attempt in range(self.max_retries):
            set_seed(table_seed + attempt)
            raw, n_in, n_out = self._generate(prompt, temperature=temperature + attempt * 0.1)
            stats["attempts"] += 1
            stats["prompt_tokens"] += n_in
            stats["output_tokens"] += n_out
            data = self._extract_json(raw)
            if data:
                break
        stats["seconds"] = time.perf_counter() - start
        stats["ok"] = data is not None
        self.table_stats.append(stats)
        if data is None:
            # Return table unchanged if all retries fail
            return table

        col_map = {c["name"]: c for c in data.get("columns", [])}
        new_columns = []
        for col in table.columns:
            aug = col_map.get(col.name, {})
            new_columns.append(Column(
                name=col.name,
                type=col.type,
                alias_vi=aug.get("alias_vi", ""),
                synonym=aug.get("synonym", []),
                sample_values=col.sample_values,
                description=aug.get("description", ""),
                is_primary_key=col.is_primary_key,
                foreign_key_to=col.foreign_key_to,
            ))
        return Table(name=table.name, alias_vi=data.get("alias_vi", ""), columns=new_columns)

    def augment_schema(self, schema: Schema) -> Schema:
        """Augment all tables in a schema."""
        self.table_stats = []
        augmented_tables = [self.augment_table(table, db_id=schema.db_id) for table in schema.tables]
        return Schema(db_id=schema.db_id, tables=augmented_tables)

    def save(self, schema: Schema, output_dir: str) -> None:
        """Save augmented schema to JSON file."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        out_path = Path(output_dir) / f"{schema.db_id}.json"
        data = {
            "db_id": schema.db_id,
            "tables": [
                {
                    "name": t.name,
                    "alias_vi": t.alias_vi,
                    "columns": [
                        {
                            "name": c.name,
                            "type": c.type,
                            "alias_vi": c.alias_vi,
                            "synonym": c.synonym,
                            "sample_values": c.sample_values,
                            "description": c.description,
                            "is_primary_key": c.is_primary_key,
                            "foreign_key_to": c.foreign_key_to,
                        }
                        for c in t.columns
                    ],
                }
                for t in schema.tables
            ],
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
