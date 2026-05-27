import os
import re
from typing import List

from utils.data_loader import Schema
from prompts.templates import build_sql_generation_prompt

GPT4O_MINI = "gpt-4.1-mini"


class SQLGenerator:
    """Unified SQL generator supporting local HuggingFace models and GPT-4o-mini."""

    def __init__(self, model_name: str, device: str = "cpu", max_new_tokens: int = 256):
        self.model_name = model_name
        self.device = device
        self.max_new_tokens = max_new_tokens
        self._is_openai = model_name == GPT4O_MINI

        if self._is_openai:
            from openai import OpenAI
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise EnvironmentError("OPENAI_API_KEY environment variable is not set.")
            self._client = OpenAI(api_key=api_key)
        else:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM
            self._torch = torch
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            # Left-pad so all sequences in a batch are right-aligned at generation start
            self.tokenizer.padding_side = "left"
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                dtype=torch.float16 if device == "cuda" else torch.float32,
                device_map=device,
            )
            self.model.eval()

    def generate(self, question: str, schema: Schema, augmented: bool) -> str:
        """Generate SQL for a single example."""
        prompt = build_sql_generation_prompt(question, schema, augmented=augmented)
        if self._is_openai:
            return self._generate_openai(prompt)
        return self._generate_local(prompt)

    def generate_batch(self, questions: List[str], schemas: List[Schema], augmented: bool) -> List[str]:
        """Generate SQL for a batch of examples (local models only)."""
        if self._is_openai:
            return [self.generate(q, s, augmented) for q, s in zip(questions, schemas)]

        prompts = [
            build_sql_generation_prompt(q, s, augmented=augmented)
            for q, s in zip(questions, schemas)
        ]
        texts = [
            self.tokenizer.apply_chat_template(
                [{"role": "user", "content": p}],
                tokenize=False,
                add_generation_prompt=True,
            )
            for p in prompts
        ]
        inputs = self.tokenizer(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=2048,
        ).to(self.device)

        input_len = inputs["input_ids"].shape[1]
        with self._torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id,
            )

        results = []
        for output in outputs:
            new_tokens = output[input_len:]
            raw = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
            results.append(self._extract_sql(raw))
        return results

    def _generate_local(self, prompt: str) -> str:
        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        with self._torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        raw = self.tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        return self._extract_sql(raw)

    def _generate_openai(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_new_tokens,
            temperature=0.0,
        )
        raw = response.choices[0].message.content or ""
        return self._extract_sql(raw)

    def _extract_sql(self, text: str) -> str:
        # Remove markdown code block if present
        text = re.sub(r"```sql\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"```", "", text)
        sql = text.strip()
        if ";" in sql:
            sql = sql[: sql.index(";") + 1]
        return sql.strip()
