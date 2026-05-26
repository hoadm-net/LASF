import json
import re
from pathlib import Path

from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

from utils.data_loader import Schema, Column, Table
from prompts.templates import build_augmentation_prompt


class SchemaAugmentor:
    def __init__(self, model_name: str = "Qwen/Qwen2.5-7B-Instruct", device: str = "cpu", max_retries: int = 3):
        self.device = device
        self.max_retries = max_retries
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map=device,
        )

    def _generate(self, prompt: str, temperature: float = 0.1) -> str:
        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=1024,
                temperature=temperature,
                do_sample=temperature > 0,
            )
        return self.tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

    def _extract_json(self, text: str) -> dict | None:
        # Extract JSON block from model output
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None

    def augment_table(self, table: Table, temperature: float = 0.1) -> Table:
        """Augment a single table with Vietnamese metadata."""
        sample_values = {col.name: col.sample_values for col in table.columns}
        prompt = build_augmentation_prompt(table.name, table.columns, sample_values)

        for attempt in range(self.max_retries):
            raw = self._generate(prompt, temperature=temperature + attempt * 0.1)
            data = self._extract_json(raw)
            if data:
                break
        else:
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
        augmented_tables = [self.augment_table(table) for table in schema.tables]
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
