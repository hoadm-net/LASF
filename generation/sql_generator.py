import os
import re
from typing import List

from utils.data_loader import Schema
from prompts.templates import build_sql_generation_prompt, count_schema_lines

GPT4O_MINI = "gpt-4.1-mini"


class SQLGenerator:
    """Unified SQL generator supporting local HuggingFace models and GPT-4o-mini."""

    def __init__(self, model_name: str, device: str = "cpu", max_new_tokens: int = 256, max_input_tokens: int = 32768):
        self.model_name = model_name
        self.device = device
        self.max_new_tokens = max_new_tokens
        self.max_input_tokens = max_input_tokens
        self._is_openai = model_name == GPT4O_MINI

        if self._is_openai:
            from openai import OpenAI
            # OpenRouter (OpenAI-compatible) if its key is set, otherwise the OpenAI API directly
            api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise EnvironmentError("Set OPENROUTER_API_KEY or OPENAI_API_KEY in .env.")
            base_url = os.environ.get("OPENAI_BASE_URL") if os.environ.get("OPENROUTER_API_KEY") else None
            self._client = OpenAI(api_key=api_key, base_url=base_url, max_retries=5)
            # Model id sent to the API, e.g. "openai/gpt-4.1-mini" on OpenRouter
            self.api_model = os.environ.get("REFERENCE_MODEL_ID", model_name) if base_url else model_name
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

    def generate(self, question: str, schema: Schema, augmented: bool, evidence: str = "") -> str:
        """Generate SQL for a single example."""
        prompt = self.build_prompt(question, schema, augmented=augmented, evidence=evidence)["prompt"]
        return self.generate_batch([prompt])[0]["pred_sql"]

    def build_prompt(self, question: str, schema: Schema, augmented: bool, evidence: str = "") -> dict:
        """Build the prompt, cutting the schema (never the question/evidence) to fit max_input_tokens.

        Returns {"prompt", "prompt_tokens", "truncated", "schema_lines_kept", "schema_lines_total"}.
        """
        total = count_schema_lines(schema, augmented)
        prompt = build_sql_generation_prompt(question, schema, augmented=augmented, evidence=evidence)
        info = {"prompt": prompt, "prompt_tokens": None, "truncated": False,
                "schema_lines_kept": total, "schema_lines_total": total}
        if self._is_openai:
            return info
        n = self._count_tokens(prompt)
        info["prompt_tokens"] = n
        if n <= self.max_input_tokens:
            return info
        # Largest number of schema lines that fits (binary search)
        lo, hi = 0, total
        while lo < hi:
            mid = (lo + hi + 1) // 2
            p = build_sql_generation_prompt(question, schema, augmented, evidence, max_schema_lines=mid)
            if self._count_tokens(p) <= self.max_input_tokens:
                lo = mid
            else:
                hi = mid - 1
        prompt = build_sql_generation_prompt(question, schema, augmented, evidence, max_schema_lines=lo)
        info.update(prompt=prompt, prompt_tokens=self._count_tokens(prompt), truncated=True, schema_lines_kept=lo)
        return info

    def _chat_text(self, prompt: str) -> str:
        return self.tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True
        )

    def _count_tokens(self, prompt: str) -> int:
        return len(self.tokenizer(self._chat_text(prompt))["input_ids"])

    def generate_batch(self, prompts: List[str]) -> List[dict]:
        """Generate SQL for a batch of already-built prompts.

        Returns one dict per prompt: {"pred_sql", "raw_output", "output_tokens"}.
        """
        if self._is_openai:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=8) as pool:
                return list(pool.map(self._generate_openai, prompts))

        texts = [self._chat_text(p) for p in prompts]
        # Prompts were already fitted to max_input_tokens by build_prompt; no truncation here
        inputs = self.tokenizer(texts, return_tensors="pt", padding=True).to(self.device)

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
            n_out = int((new_tokens != self.tokenizer.pad_token_id).sum())
            raw = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
            results.append({"pred_sql": self._extract_sql(raw), "raw_output": raw, "output_tokens": n_out})
        return results

    def _generate_openai(self, prompt: str) -> dict:
        # On OpenRouter, pin the provider to OpenAI so all requests hit the same backend
        extra = {"provider": {"order": ["OpenAI"], "allow_fallbacks": False}} if self.api_model != self.model_name else None
        response = self._client.chat.completions.create(
            model=self.api_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_new_tokens,
            temperature=0.0,
            extra_body=extra,
        )
        raw = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        return {
            "pred_sql": self._extract_sql(raw),
            "raw_output": raw,
            "output_tokens": getattr(usage, "completion_tokens", None),
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "provider": getattr(response, "provider", None),
        }

    def _extract_sql(self, text: str) -> str:
        # Remove markdown code block if present
        text = re.sub(r"```sql\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"```", "", text)
        sql = text.strip()
        if ";" in sql:
            sql = sql[: sql.index(";") + 1]
        return sql.strip()
