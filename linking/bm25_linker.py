"""Lexical baseline for schema linking: BM25 over the same column documents as SchemaLinker."""

import re

import numpy as np
from rank_bm25 import BM25Okapi

from utils.data_loader import Schema, Table, Column
from linking.schema_linker import SchemaLinker, select_top_k


def tokenize(text: str) -> list[str]:
    # split snake_case / camelCase identifiers, then lowercase word tokens (Unicode-aware)
    text = text.replace("_", " ")
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return re.findall(r"\w+", text.lower())


class BM25Linker:
    def __init__(self, top_k: int = 10, top_k_ratio: float | None = None):
        self.top_k = top_k
        self.top_k_ratio = top_k_ratio
        self._index_cache: dict[tuple, BM25Okapi] = {}

    k_for = SchemaLinker.k_for

    def score_columns(self, question: str, schema: Schema) -> tuple[list[tuple[Table, Column]], np.ndarray]:
        column_index = [(t, c) for t in schema.tables for c in t.columns]
        docs = tuple(SchemaLinker._build_column_text(None, t, c) for t, c in column_index)
        key = (schema.db_id, hash(docs))
        if key not in self._index_cache:
            self._index_cache[key] = BM25Okapi([tokenize(d) for d in docs])
        return column_index, np.asarray(self._index_cache[key].get_scores(tokenize(question)))

    def retrieve(self, question: str, schema: Schema, top_k: int | None = None) -> Schema:
        column_index, scores = self.score_columns(question, schema)
        if not column_index:
            return schema
        k = top_k if top_k is not None else self.k_for(len(column_index))
        return select_top_k(schema, column_index, scores, k)
