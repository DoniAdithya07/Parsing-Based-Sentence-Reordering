from __future__ import annotations

from typing import List, Tuple


def _sentence_length_score(sentence: str) -> int:
    return len(sentence.split())


def _overlap_score(a: str, b: str) -> float:
    a_words = set(a.lower().split())
    b_words = set(b.lower().split())
    if not a_words or not b_words:
        return 0.0
    return len(a_words & b_words) / len(a_words | b_words)


def _sequence_coherence(sentences: List[str]) -> float:
    if len(sentences) < 2:
        return 0.0
    scores = []
    for i in range(len(sentences) - 1):
        scores.append(_overlap_score(sentences[i], sentences[i + 1]))
    return sum(scores) / len(scores)


def baseline_reorder(sentences: List[str]) -> Tuple[List[str], float]:
    """Baseline reorder: sort shorter to longer and compute overlap coherence."""
    ordered = sorted(sentences, key=_sentence_length_score)
    coherence = _sequence_coherence(ordered)
    return ordered, round(coherence, 3)
