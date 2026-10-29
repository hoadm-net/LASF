import numpy as np
from sentence_transformers import SentenceTransformer

from utils.data_loader import Schema, Table, Column


class SchemaLinker:
    def __init__(self, model_name: str = "intfloat/multilingual-e5-large", device: str = "cpu", top_k: int = 10,
                 top_k_ratio: float | None = None):
        self.model = SentenceTransformer(model_name, device=device)
        self.top_k = top_k
        self.top_k_ratio = top_k_ratio  # if set, k = round(ratio * #columns) per database
        self._passage_cache: dict[tuple, np.ndarray] = {}

    def k_for(self, n_columns: int) -> int:
        if self.top_k_ratio is not None:
            return max(1, round(self.top_k_ratio * n_columns))
        return self.top_k

    def _build_column_text(self, table: Table, col: Column) -> str:
        """Build text representation of a column for embedding."""
        parts = [f"{table.name} {col.name}"]
        if table.alias_vi:
            parts.append(table.alias_vi)
        if col.alias_vi:
            parts.append(col.alias_vi)
        if col.synonym:
            parts.extend(col.synonym)
        if col.description:
            parts.append(col.description)
        return " ".join(parts)

    def _build_query_text(self, question: str) -> str:
        # multilingual-e5 expects "query: " prefix for queries
        return f"query: {question}"

    def _build_passage_text(self, text: str) -> str:
        # multilingual-e5 expects "passage: " prefix for documents
        return f"passage: {text}"

    def score_columns(self, question: str, schema: Schema) -> tuple[list[tuple[Table, Column]], np.ndarray]:
        """Cosine similarity between the question and every column document of the schema."""
        column_index = [(t, c) for t in schema.tables for c in t.columns]
        texts = tuple(self._build_passage_text(self._build_column_text(t, c)) for t, c in column_index)
        key = (schema.db_id, hash(texts))
        if key not in self._passage_cache:  # column documents depend only on the schema
            self._passage_cache[key] = self.model.encode(list(texts), normalize_embeddings=True, batch_size=64)
        query_emb = self.model.encode(self._build_query_text(question), normalize_embeddings=True)
        return column_index, np.dot(self._passage_cache[key], query_emb)

    def retrieve(self, question: str, schema: Schema, top_k: int | None = None) -> Schema:
        """
        Return a filtered Schema containing the top-k relevant columns, plus the primary-key
        and foreign-key columns of every table that has at least one selected column.
        """
        column_index, scores = self.score_columns(question, schema)
        if not column_index:
            return schema
        k = top_k if top_k is not None else self.k_for(len(column_index))
        top_indices = np.argsort(scores)[::-1][:k]

        # Collect selected tables and always-include PKs
        selected_tables: dict[str, set[str]] = {}
        for idx in top_indices:
            table, col = column_index[idx]
            selected_tables.setdefault(table.name, set()).add(col.name)

        # Include primary keys of selected tables
        for table in schema.tables:
            if table.name in selected_tables:
                for col in table.columns:
                    if col.is_primary_key:
                        selected_tables[table.name].add(col.name)
                    # Include FK columns to preserve join context
                    if col.foreign_key_to:
                        selected_tables[table.name].add(col.name)

        # Build filtered schema
        filtered_tables = []
        for table in schema.tables:
            if table.name not in selected_tables:
                continue
            selected_cols = selected_tables[table.name]
            filtered_cols = [c for c in table.columns if c.name in selected_cols]
            filtered_tables.append(Table(
                name=table.name,
                alias_vi=table.alias_vi,
                columns=filtered_cols,
            ))

        return Schema(db_id=schema.db_id, tables=filtered_tables)
