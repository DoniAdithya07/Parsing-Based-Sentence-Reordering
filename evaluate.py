from __future__ import annotations

from collections import Counter, defaultdict, deque
from typing import List


def simple_exact_match(predicted: List[str], gold: List[str]) -> float:
    if not gold:
        return 0.0
    matches = sum(1 for p, g in zip(predicted, gold) if p == g)
    return matches / len(gold)


def perfect_match_ratio(predicted: List[str], gold: List[str]) -> float:
    if not gold:
        return 0.0
    return 1.0 if predicted == gold else 0.0


def _align_to_gold_positions(predicted: List[str], gold: List[str]) -> List[int]:
    buckets = defaultdict(deque)
    for idx, sentence in enumerate(gold):
        buckets[sentence].append(idx)

    positions: List[int] = []
    for sentence in predicted:
        if buckets[sentence]:
            positions.append(buckets[sentence].popleft())
    return positions


def _same_sentence_multiset(predicted: List[str], gold: List[str]) -> bool:
    return len(predicted) == len(gold) and Counter(predicted) == Counter(gold)


def pairwise_accuracy(predicted: List[str], gold: List[str]) -> float:
    if not _same_sentence_multiset(predicted, gold):
        return 0.0

    positions = _align_to_gold_positions(predicted, gold)
    n = len(positions)
    if n < 2:
        return 0.0

    total_pairs = n * (n - 1) // 2
    correct_pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            if positions[i] < positions[j]:
                correct_pairs += 1
    return correct_pairs / total_pairs


def kendall_tau(predicted: List[str], gold: List[str]) -> float:
    if not _same_sentence_multiset(predicted, gold):
        return 0.0

    positions = _align_to_gold_positions(predicted, gold)
    n = len(positions)
    if n < 2:
        return 0.0

    concordant = 0
    discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            if positions[i] < positions[j]:
                concordant += 1
            elif positions[i] > positions[j]:
                discordant += 1

    denom = concordant + discordant
    if denom == 0:
        return 0.0
    return (concordant - discordant) / denom


def evaluate_sequence(predicted: List[str], gold: List[str]):
    return {
        "exact_match": round(simple_exact_match(predicted, gold), 4),
        "pmr": round(perfect_match_ratio(predicted, gold), 4),
        "pairwise_accuracy": round(pairwise_accuracy(predicted, gold), 4),
        "kendall_tau": round(kendall_tau(predicted, gold), 4),
    }
