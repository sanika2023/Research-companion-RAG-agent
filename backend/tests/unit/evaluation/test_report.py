from app.evaluation.report import retrieval_table


def test_retrieval_table_has_one_row_per_method_with_hit_rates_and_mrr() -> None:
    table = retrieval_table({"keyword": [1, None], "hybrid": [1, 2]}, ks=(1, 3))

    lines = table.splitlines()
    assert lines[0] == "| Method | Hit@1 | Hit@3 | MRR |"
    assert lines[2] == "| keyword | 0.50 | 0.50 | 0.50 |"
    assert lines[3] == "| hybrid | 0.50 | 1.00 | 0.75 |"
