import numpy as np
from sentence_transformers import SentenceTransformer

from utils.data_loader import Schema, Table, Column


class SchemaLinker:
    def __init__(self, model_name: str = "intfloat/multilingual-e5-large", device: str = "cpu", top_k: int = 10):
        self.model = SentenceTransformer(model_name, device=device)
        self.top_k = top_k

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

    def retrieve(self, question: str, schema: Schema) -> Schema:
        """
        Return a filtered Schema containing only the top-k relevant columns
        (and all columns of any table that has at least one selected column).
        """
        # Build column index
        column_index = []  # (table, column, text)
        for table in schema.tables:
            for col in table.columns:
                text = self._build_column_text(table, col)
                column_index.append((table, col, text))

        if not column_index:
            return schema

        # Encode query and passages
        query_emb = self.model.encode(
            self._build_query_text(question),
            normalize_embeddings=True,
        )
        passage_texts = [self._build_passage_text(t) for _, _, t in column_index]
        passage_embs = self.model.encode(passage_texts, normalize_embeddings=True, batch_size=64)

        # Cosine similarity (already normalized → dot product)
        scores = np.dot(passage_embs, query_emb)
        top_indices = np.argsort(scores)[::-1][: self.top_k]

        # Collect selected tables and always-include PKs
        selected_tables: dict[str, set[str]] = {}
        for idx in top_indices:
            table, col, _ = column_index[idx]
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
