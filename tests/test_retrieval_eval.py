from scripts.eval_retrieval import evaluate_model, load_catalog, load_queries


def test_multilingual_e5_hit_at_three_gate():
    metrics = evaluate_model(
        "intfloat/multilingual-e5-small",
        load_queries(),
        load_catalog(),
    )

    assert metrics["hit@3"] >= 0.9, (
        f"multilingual-e5-small hit@3 was {metrics['hit@3']:.3f}, "
        "expected at least 0.900"
    )
