from __future__ import annotations

from typing import List


def simple_exact_match(predicted: List[str], gold: List[str]) -> float:
    if not gold:
        return 0.0
    matches = sum(1 for p, g in zip(predicted, gold) if p == g)
    return matches / len(gold)
