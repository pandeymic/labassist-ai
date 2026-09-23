"""Evaluate catalog retrieval with the legacy and multilingual embedding models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "test_catalog.json"
EVAL_PATH = ROOT / "tests" / "retrieval_eval.jsonl"


def load_catalog() -> list[dict[str, Any]]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def load_queries() -> list[dict[str, str]]:
    return [
        json.loads(line)
        for line in EVAL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def catalog_document(record: dict[str, Any]) -> str:
    aliases = [
        *record.get("aliases", []),
        *record.get("aliases_hi", []),
        *record.get("aliases_hinglish", []),
    ]
    return (
        f"Test Name: {record['name']}\n"
        f"Aliases: {', '.join(aliases)}\n"
        f"Category: {record['category']} | Price: ₹{record['price_inr']} INR\n"
        f"Fasting Required: {record['fasting_required']} ({record['fasting_hours']} hours)\n"
        f"Sample Type: {record['sample_type']} | Turnaround Time: {record['turnaround_time']}\n"
        f"Description: {record['description']}"
    )


def evaluate_model(model_name: str, queries: list[dict[str, str]], records: list[dict[str, Any]]) -> dict[str, float]:
    model = SentenceTransformer(model_name)
    documents = [catalog_document(record) for record in records]
    is_e5 = "multilingual-e5" in model_name.lower()
    document_inputs = [f"passage: {document}" for document in documents] if is_e5 else documents
    query_inputs = [f"query: {item['query']}" for item in queries] if is_e5 else [item["query"] for item in queries]

    document_embeddings = model.encode(
        document_inputs,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    query_embeddings = model.encode(
        query_inputs,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    hits_at_1 = 0
    hits_at_3 = 0
    id_by_index = [record["test_id"] for record in records]
    for query_embedding, item in zip(query_embeddings, queries):
        scores = document_embeddings @ query_embedding
        ranked_indexes = scores.argsort()[::-1]
        ranked_ids = [id_by_index[index] for index in ranked_indexes]
        expected_id = item["expected_test_id"]
        hits_at_1 += ranked_ids[0] == expected_id
        hits_at_3 += expected_id in ranked_ids[:3]

    total = len(queries)
    return {"hit@1": hits_at_1 / total, "hit@3": hits_at_3 / total}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-model", default="all-MiniLM-L6-v2")
    parser.add_argument("--new-model", default="intfloat/multilingual-e5-small")
    args = parser.parse_args()

    queries = load_queries()
    records = load_catalog()
    print(f"Evaluating {len(queries)} queries against {len(records)} catalog records")
    for label, model_name in (("old", args.old_model), ("new", args.new_model)):
        metrics = evaluate_model(model_name, queries, records)
        print(f"{label:>3} | {model_name:<36} hit@1={metrics['hit@1']:.3f} hit@3={metrics['hit@3']:.3f}")


if __name__ == "__main__":
    main()
