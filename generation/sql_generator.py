import re

from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

from utils.data_loader import Schema
from prompts.templates import build_sql_generation_prompt


class SQLGenerator:
    def __init__(self, model_name: str, device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map=device,
        )

    def generate(self, question: str, schema: Schema, augmented: bool) -> str:
        prompt = build_sql_generation_prompt(question, schema, augmented=augmented)
        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=False,
            )
        raw = self.tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        return self._extract_sql(raw)

    def _extract_sql(self, text: str) -> str:
        # Remove markdown code block if present
        text = re.sub(r"```sql\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"```", "", text)
        # Take content up to first double newline or semicolon
        sql = text.strip()
        if ";" in sql:
            sql = sql[: sql.index(";") + 1]
        return sql.strip()
