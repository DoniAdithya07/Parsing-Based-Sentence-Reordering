from __future__ import annotations

from typing import List, Tuple

import spacy


_NLP = None


def get_spacy_model():
    """Load spaCy model once and reuse it."""
    global _NLP
    if _NLP is None:
        try:
            _NLP = spacy.load("en_core_web_sm")
        except OSError:
            from spacy.cli import download

            download("en_core_web_sm")
            _NLP = spacy.load("en_core_web_sm")
    return _NLP


def _parse_score(doc) -> float:
    # Simple, explainable score using dependency roles and POS tags.
    subjects = sum(1 for t in doc if t.dep_ in {"nsubj", "nsubjpass"})
    objects = sum(1 for t in doc if t.dep_ in {"dobj", "obj", "iobj"})
    roots = sum(1 for t in doc if t.dep_ == "ROOT")
    proper_nouns = sum(1 for t in doc if t.pos_ == "PROPN")
    pronouns = sum(1 for t in doc if t.pos_ == "PRON")
    return subjects + objects + roots + proper_nouns - pronouns


def _normalize(scores: List[float]) -> List[float]:
    if not scores:
        return scores
    min_s = min(scores)
    max_s = max(scores)
    if min_s == max_s:
        return [0.5 for _ in scores]
    return [(s - min_s) / (max_s - min_s) for s in scores]


def parser_reorder(sentences: List[str], nlp) -> Tuple[List[str], float]:
    """Parsing-based reorder using lightweight dependency signals."""
    docs = [nlp(s) for s in sentences]
    scores = [_parse_score(doc) for doc in docs]
    normalized = _normalize(scores)

    ranked = list(zip(sentences, normalized))
    ranked.sort(key=lambda x: x[1], reverse=True)
    ordered = [s for s, _ in ranked]

    confidence = sum(normalized) / len(normalized) if normalized else 0.0
    return ordered, round(confidence, 3)
