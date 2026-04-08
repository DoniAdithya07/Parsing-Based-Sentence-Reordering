from evaluate import evaluate_sequence, kendall_tau, pairwise_accuracy, perfect_match_ratio


def test_perfect_sequence_metrics_are_one():
    gold = ["A", "B", "C", "D"]
    metrics = evaluate_sequence(gold, gold)

    assert metrics["exact_match"] == 1.0
    assert metrics["pmr"] == 1.0
    assert metrics["pairwise_accuracy"] == 1.0
    assert metrics["kendall_tau"] == 1.0


def test_reversed_sequence_metrics_are_low():
    gold = ["A", "B", "C", "D"]
    predicted = list(reversed(gold))

    assert perfect_match_ratio(predicted, gold) == 0.0
    assert pairwise_accuracy(predicted, gold) == 0.0
    assert kendall_tau(predicted, gold) == -1.0


def test_partial_sequence_metrics():
    gold = ["A", "B", "C", "D"]
    predicted = ["A", "C", "B", "D"]

    assert perfect_match_ratio(predicted, gold) == 0.0
    assert pairwise_accuracy(predicted, gold) == 5 / 6
    assert kendall_tau(predicted, gold) == 2 / 3
