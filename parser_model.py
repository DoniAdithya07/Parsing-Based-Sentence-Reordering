from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List, Set, Tuple

import spacy


_NLP = None
START_CUES = (
    "first",
    "firstly",
    "to begin",
    "initially",
    "at first",
    "in the beginning",
)
MIDDLE_CUES = (
    "then",
    "next",
    "afterward",
    "afterwards",
    "subsequently",
    "meanwhile",
    "later",
    "in addition",
    "also",
)
END_CUES = (
    "finally",
    "lastly",
    "in conclusion",
    "to conclude",
    "overall",
    "in summary",
)
CONNECTIVE_CUES = (
    "however",
    "therefore",
    "thus",
    "consequently",
    "moreover",
    "furthermore",
    "but",
    "yet",
)
PRONOUN_WORDS = {
    "i",
    "you",
    "he",
    "she",
    "it",
    "we",
    "they",
    "me",
    "him",
    "her",
    "us",
    "them",
    "my",
    "your",
    "his",
    "its",
    "our",
    "their",
    "mine",
    "yours",
    "hers",
    "ours",
    "theirs",
    "this",
    "that",
    "these",
    "those",
}
DISCOURSE_STARTERS = ("meanwhile", "however", "nevertheless", "nonetheless", "but", "yet")
TOPIC_POLICY = "policy"
TOPIC_ECONOMY = "economy"
TOPIC_LEGAL = "legal"
TOPIC_CORPORATE = "corporate"
TOPIC_TECHNICAL = "technical"
TOPIC_GENERAL = "general"
TOPIC_PRIORITY = {
    TOPIC_POLICY: 0,
    TOPIC_ECONOMY: 1,
    TOPIC_LEGAL: 2,
    TOPIC_CORPORATE: 3,
    TOPIC_TECHNICAL: 4,
    TOPIC_GENERAL: 5,
}
TOPIC_KEYWORDS = {
    TOPIC_POLICY: {
        "policy",
        "sanction",
        "sanctions",
        "tariff",
        "official",
        "officials",
        "government",
        "election",
        "elections",
        "protectionist",
        "curbs",
        "diplomatic",
        "talks",
        "negotiation",
        "minister",
        "state",
        "friction",
        "rift",
        "curb",
        "curbs",
        "threat",
        "threatened",
        "war",
        "gulf",
        "iran",
        "iraq",
        "japan",
        "kuwait",
        "washington",
        "usa",
        "us",
    },
    TOPIC_ECONOMY: {
        "economic",
        "economy",
        "market",
        "markets",
        "export",
        "exports",
        "import",
        "imports",
        "trading",
        "trade",
        "oil",
        "coffee",
        "rubber",
        "tonnes",
        "rupiah",
        "inflation",
        "gdp",
        "growth",
        "contracts",
        "commodity",
        "commodities",
    },
    TOPIC_LEGAL: {
        "lawsuit",
        "lawsuits",
        "law",
        "legal",
        "court",
        "judge",
        "case",
        "filed",
        "sued",
        "hearing",
        "appeal",
        "plaintiff",
        "defendant",
        "sequestered",
    },
    TOPIC_CORPORATE: {
        "corp",
        "corporation",
        "company",
        "companies",
        "ltd",
        "inc",
        "bank",
        "shares",
        "stake",
        "acquisition",
        "merger",
        "deal",
        "bid",
        "branch",
        "smc",
    },
    TOPIC_TECHNICAL: {
        "technical",
        "technology",
        "software",
        "hardware",
        "system",
        "systems",
        "model",
        "models",
        "algorithm",
        "algorithms",
        "engineering",
        "pipeline",
    },
}
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2}|21\d{2})\b")


@dataclass
class SentenceUnit:
    index: int
    text: str
    local_score: float
    keywords: Set[str]
    entities: Set[str]
    subjects: Set[str]
    starts_with_pronoun: bool
    stage: int  # 0=start, 1=middle, 2=end
    topic: str


def get_spacy_model():
    """Load spaCy model once and reuse it."""
    global _NLP
    if _NLP is None:
        try:
            _NLP = spacy.load("en_core_web_sm")
        except OSError:
            # Streamlit/serverless environments may miss the packaged model.
            # Fall back to a blank English pipeline so the app remains usable.
            try:
                from spacy.cli import download

                download("en_core_web_sm")
                _NLP = spacy.load("en_core_web_sm")
            except Exception:
                _NLP = spacy.blank("en")
                if "sentencizer" not in _NLP.pipe_names:
                    _NLP.add_pipe("sentencizer")
    return _NLP


def spacy_engine_mode(nlp) -> str:
    pipe_names = set(getattr(nlp, "pipe_names", []) or [])
    if "parser" in pipe_names:
        return "dependency_parser"
    if "tagger" in pipe_names:
        return "pos_tagger_only"
    return "tokenizer_only"


def _token_norm(token) -> str:
    lemma = str(getattr(token, "lemma_", "") or "").strip().lower()
    text = str(getattr(token, "text", "") or "").strip().lower()
    norm = lemma if lemma and lemma != "-pron-" else text
    return norm


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _starts_with_any(text: str, cues: Tuple[str, ...]) -> bool:
    normalized = text.lower().lstrip(" \t\"'([{")
    return any(normalized.startswith(cue) for cue in cues)


def _sentence_stage(text: str) -> int:
    if _starts_with_any(text, START_CUES):
        return 0
    if _starts_with_any(text, END_CUES):
        return 2
    return 1


def _position_prior(stage: int, position: int, total: int) -> float:
    if total <= 1:
        return 1.0
    ratio = position / (total - 1)
    ideal = 0.15
    if stage == 1:
        ideal = 0.50
    elif stage == 2:
        ideal = 0.85
    distance = abs(ratio - ideal)
    return max(0.0, 1.0 - min(1.0, distance * 1.4))


def _parse_score(doc) -> float:
    # Simple, explainable score using dependency roles and POS tags.
    subjects = sum(1 for t in doc if str(getattr(t, "dep_", "")) in {"nsubj", "nsubjpass"})
    objects = sum(1 for t in doc if str(getattr(t, "dep_", "")) in {"dobj", "obj", "iobj"})
    roots = sum(1 for t in doc if str(getattr(t, "dep_", "")) == "ROOT")
    proper_nouns = sum(1 for t in doc if str(getattr(t, "pos_", "")) == "PROPN")
    pronouns = sum(1 for t in doc if str(getattr(t, "pos_", "")) == "PRON")
    verbs = sum(1 for t in doc if str(getattr(t, "pos_", "")) in {"VERB", "AUX"})
    return subjects + objects + roots + proper_nouns + 0.5 * verbs - pronouns


def _normalize(scores: List[float]) -> List[float]:
    if not scores:
        return scores
    min_s = min(scores)
    max_s = max(scores)
    if min_s == max_s:
        return [0.5 for _ in scores]
    return [(s - min_s) / (max_s - min_s) for s in scores]


def _extract_keywords(doc) -> Set[str]:
    keywords: Set[str] = set()
    for token in doc:
        norm = _token_norm(token)
        if not norm.isalpha() or len(norm) < 3:
            continue
        if bool(getattr(token, "is_stop", False)):
            continue
        pos = str(getattr(token, "pos_", ""))
        if pos in {"NOUN", "PROPN", "VERB", "ADJ"} or not pos:
            keywords.add(norm)
    return keywords


def _extract_entities(doc) -> Set[str]:
    entities: Set[str] = set()
    doc_ents = list(getattr(doc, "ents", []) or [])
    if doc_ents:
        for ent in doc_ents:
            text = " ".join(str(getattr(ent, "text", "")).split()).strip().lower()
            if text:
                entities.add(text)
        if entities:
            return entities

    for token in doc:
        norm = _token_norm(token)
        if not norm.isalpha() or len(norm) < 3:
            continue
        pos = str(getattr(token, "pos_", ""))
        if pos in {"NOUN", "PROPN"}:
            entities.add(norm)
    return entities


def _extract_subjects(doc) -> Set[str]:
    subjects: Set[str] = set()
    for token in doc:
        dep = str(getattr(token, "dep_", ""))
        if dep in {"nsubj", "nsubjpass", "csubj", "csubjpass"}:
            norm = _token_norm(token)
            if norm.isalpha() and len(norm) >= 2:
                subjects.add(norm)

    if subjects:
        return subjects

    # Fallback when parser dependency labels are unavailable.
    for token in doc:
        norm = _token_norm(token)
        if not norm.isalpha() or len(norm) < 2:
            continue
        if norm in PRONOUN_WORDS:
            continue
        subjects.add(norm)
        break
    return subjects


def _starts_with_pronoun(doc) -> bool:
    for token in doc:
        norm = _token_norm(token)
        if not norm:
            continue
        if not norm.isalpha():
            continue
        pos = str(getattr(token, "pos_", ""))
        if pos:
            return pos == "PRON"
        return norm in PRONOUN_WORDS
    return False


def _cue_bonus(text: str) -> float:
    lowered = text.lower()
    bonus = 0.0
    if _starts_with_any(lowered, START_CUES):
        bonus += 0.8
    if _starts_with_any(lowered, MIDDLE_CUES):
        bonus += 0.5
    if _starts_with_any(lowered, END_CUES):
        bonus += 0.7
    if _starts_with_any(lowered, CONNECTIVE_CUES):
        bonus += 0.2
    return bonus


def _topic_rank(topic: str) -> int:
    return TOPIC_PRIORITY.get(topic, TOPIC_PRIORITY[TOPIC_GENERAL])


def _classify_topic(text: str, keywords: Set[str], entities: Set[str]) -> str:
    lowered = text.lower()
    scores: Dict[str, float] = {topic: 0.0 for topic in TOPIC_PRIORITY.keys()}

    for topic, vocab in TOPIC_KEYWORDS.items():
        scores[topic] += sum(1.0 for word in keywords if word in vocab)

    # Phrase/indicator boosts.
    if any(token in lowered for token in ("trade sanctions", "protectionist", "foreign policy", "elections", "official said")):
        scores[TOPIC_POLICY] += 2.0
    if any(token in lowered for token in ("trade friction", "u.s.", "japan", "iran-iraq", "gulf", "threatened trade sanctions", "curbs on imports")):
        scores[TOPIC_POLICY] += 2.6
    if any(token in lowered for token in ("economic activity", "export", "imports", "calendar", "tonnes", "rupiah", "contracts traded")):
        scores[TOPIC_ECONOMY] += 2.0
    if any(token in lowered for token in ("lawsuit", "lawsuits", "court", "legal", "sequestered shares")):
        scores[TOPIC_LEGAL] += 2.5
    if any(token in lowered for token in ("corp", "company", "ltd", "inc", "bank", "share", "bid", "deal", "branch")):
        scores[TOPIC_CORPORATE] += 1.8
    if any(token in lowered for token in ("technology", "technical", "model", "algorithm", "software", "hardware", "pipeline")):
        scores[TOPIC_TECHNICAL] += 2.0

    # Named organizations often indicate policy/corporate context.
    if any(entity.isupper() and len(entity) >= 3 for entity in entities):
        scores[TOPIC_POLICY] += 0.5
        scores[TOPIC_CORPORATE] += 0.5

    best_topic = max(scores.keys(), key=lambda topic: (scores[topic], -_topic_rank(topic)))
    if scores[best_topic] <= 0:
        return TOPIC_GENERAL
    return best_topic


def _build_docs(sentences: List[str], nlp):
    if hasattr(nlp, "pipe"):
        try:
            return list(nlp.pipe(sentences))
        except Exception:
            pass
    return [nlp(sentence) for sentence in sentences]


def _continuity(prev: SentenceUnit, curr: SentenceUnit) -> float:
    keyword_overlap = _jaccard(prev.keywords, curr.keywords)
    entity_overlap = _jaccard(prev.entities, curr.entities)
    subject_overlap = _jaccard(prev.subjects, curr.subjects)
    return max(keyword_overlap, entity_overlap, subject_overlap)


def _entity_overlap_count(prev: SentenceUnit, curr: SentenceUnit) -> int:
    return len(prev.entities & curr.entities)


def _subject_overlap_count(prev: SentenceUnit, curr: SentenceUnit) -> int:
    return len(prev.subjects & curr.subjects)


def _pronoun_penalty(prev: SentenceUnit, curr: SentenceUnit) -> float:
    if not curr.starts_with_pronoun:
        return 0.0

    has_reference = bool(prev.entities or prev.subjects or (prev.entities & curr.entities) or (prev.subjects & curr.subjects))
    return 0.0 if has_reference else -1.0


def _discourse_start_penalty(unit: SentenceUnit) -> float:
    text = unit.text.lower().lstrip(" \t\"'([{")
    return -1.0 if text.startswith(DISCOURSE_STARTERS) else 0.0


def _position_bias(unit: SentenceUnit, position: int) -> float:
    score = 0.0
    if position != 0:
        return score

    raw = unit.text.strip()
    letters = [ch for ch in raw if ch.isalpha()]
    if letters and raw.isupper():
        score += 2.0

    lowered = raw.lower()
    if "said" in lowered:
        score -= 1.0
    if lowered.startswith(("meanwhile", "however")):
        score -= 2.0
    return score


def _pair_score(prev: SentenceUnit, curr: SentenceUnit) -> float:
    score = 0.0
    score += float(_entity_overlap_count(prev, curr)) * 2.0
    score += float(_subject_overlap_count(prev, curr)) * 1.5
    score += _pronoun_penalty(prev, curr)
    if prev.topic == curr.topic:
        score += 3.0
        if prev.topic != TOPIC_GENERAL:
            score += 0.8
    else:
        score -= 1.0

    curr_text = curr.text.lower()
    if "said" in curr_text or "told" in curr_text or "according to" in curr_text:
        if prev.entities or prev.subjects:
            score += 1.0

    # Temporal/logical flow preference.
    prev_stage, prev_rel, prev_year = _temporal_key(prev)
    curr_stage, curr_rel, curr_year = _temporal_key(curr)
    if prev_stage <= curr_stage:
        score += 0.6
    else:
        score -= 0.6

    if prev_rel <= curr_rel:
        score += 0.25
    else:
        score -= 0.25

    if prev_year != 9999 and curr_year != 9999:
        if prev_year <= curr_year:
            score += 0.20
        else:
            score -= 0.20
    return score


def _start_sentence_score(unit: SentenceUnit) -> float:
    score = 0.0
    score += _discourse_start_penalty(unit)
    score += _position_bias(unit, 0)
    if unit.starts_with_pronoun:
        score -= 0.8
    score += 0.15 * unit.local_score
    return score


def _build_topic_components(units: List[SentenceUnit]) -> List[List[int]]:
    if len(units) <= 1:
        return [[u.index] for u in units]

    parent: Dict[int, int] = {u.index: u.index for u in units}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra = find(a)
        rb = find(b)
        if ra != rb:
            parent[rb] = ra

    for i, left in enumerate(units):
        for j in range(i + 1, len(units)):
            right = units[j]
            sim = _continuity(left, right)
            # Strong topic tie.
            if sim >= 0.08:
                union(left.index, right.index)
                continue
            # Allow softer ties for pronoun-linked continuation.
            if (left.starts_with_pronoun or right.starts_with_pronoun) and sim >= 0.03:
                union(left.index, right.index)

    groups: Dict[int, List[int]] = {}
    for unit in units:
        root = find(unit.index)
        groups.setdefault(root, []).append(unit.index)
    return list(groups.values())


def _topic_connectivity(units: List[SentenceUnit]) -> Dict[int, float]:
    if len(units) <= 1:
        return {u.index: 0.5 for u in units}

    connectivity: Dict[int, float] = {}
    for unit in units:
        scores = []
        for other in units:
            if other.index == unit.index:
                continue
            scores.append(_continuity(unit, other))
        connectivity[unit.index] = sum(scores) / len(scores) if scores else 0.0
    return connectivity


def _average_pairwise_continuity(units: List[SentenceUnit]) -> float:
    if len(units) < 2:
        return 1.0

    scores: List[float] = []
    for i, left in enumerate(units):
        for j in range(i + 1, len(units)):
            right = units[j]
            scores.append(_continuity(left, right))
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _has_explicit_temporal_chain(units: List[SentenceUnit]) -> bool:
    cue_hits = 0
    for unit in units:
        text = unit.text.lower()
        if _starts_with_any(text, START_CUES) or _starts_with_any(text, MIDDLE_CUES) or _starts_with_any(text, END_CUES):
            cue_hits += 1
    return cue_hits >= 2


def _has_strong_pronoun_link(units: List[SentenceUnit]) -> bool:
    for curr in units:
        if not curr.starts_with_pronoun:
            continue
        best = 0.0
        for other in units:
            if other.index == curr.index:
                continue
            if other.starts_with_pronoun:
                continue
            best = max(best, _continuity(other, curr))
        if best >= 0.06:
            return True
    return False


def _has_topic_signal(units: List[SentenceUnit]) -> bool:
    labeled = [u for u in units if u.topic != TOPIC_GENERAL]
    if len(labeled) >= 2:
        return True
    return any(u.topic in {TOPIC_POLICY, TOPIC_ECONOMY, TOPIC_LEGAL, TOPIC_CORPORATE, TOPIC_TECHNICAL} for u in units)


def _is_independent(units: List[SentenceUnit]) -> bool:
    topics = [u.topic for u in units]
    return len(set(topics)) > 3


def _should_reorder(units: List[SentenceUnit]) -> bool:
    topics = [u.topic for u in units]
    if len(set(topics)) >= 4:
        return False
    return True


def _entity_chain_bonus(sequence: List[SentenceUnit]) -> float:
    counts: Dict[str, int] = {}
    for unit in sequence:
        for ent in unit.entities:
            counts[ent] = counts.get(ent, 0) + 1
    return float(sum(v for v in counts.values() if v > 1))


def _chain_bonus_delta(entity_counts: Dict[str, int], curr: SentenceUnit) -> Tuple[Dict[str, int], float]:
    next_counts = dict(entity_counts)
    delta = 0.0
    for ent in curr.entities:
        old = next_counts.get(ent, 0)
        new = old + 1
        next_counts[ent] = new
        if old == 1:
            delta += 2.0
        elif old >= 2:
            delta += 1.0
    return next_counts, delta


def _temporal_key(unit: SentenceUnit) -> Tuple[int, int, int]:
    text = unit.text.lower()
    stage = unit.stage
    if _starts_with_any(text, START_CUES):
        stage = 0
    elif _starts_with_any(text, END_CUES):
        stage = 2
    elif _starts_with_any(text, MIDDLE_CUES):
        stage = 1

    rel_time = 0
    if any(token in text for token in ("last", "earlier", "previous", "ago", "before")):
        rel_time = -1
    elif any(token in text for token in ("next", "future", "upcoming", "will ")):
        rel_time = 1

    year_match = YEAR_RE.findall(text)
    if year_match:
        year = min(int(y) for y in year_match)
    else:
        year = 9999
    return (stage, rel_time, year)


def _transition_score(prev: SentenceUnit, curr: SentenceUnit, position: int, total: int) -> float:
    lexical_flow = _jaccard(prev.keywords, curr.keywords)
    entity_flow = _jaccard(prev.entities, curr.entities)
    continuity = max(lexical_flow, entity_flow)

    if curr.starts_with_pronoun:
        pronoun_flow = 1.0 if continuity >= 0.08 else 0.0
    else:
        pronoun_flow = 0.6

    if prev.stage <= curr.stage:
        stage_flow = 1.0
    else:
        stage_flow = 0.15

    position_flow = _position_prior(curr.stage, position, total)

    topic_flow = 1.0 if continuity >= 0.06 else 0.15

    score = (
        0.30 * lexical_flow
        + 0.25 * entity_flow
        + 0.17 * pronoun_flow
        + 0.16 * stage_flow
        + 0.07 * position_flow
        + 0.05 * topic_flow
    )

    if continuity < 0.03:
        score -= 0.10
    if curr.starts_with_pronoun and continuity < 0.08:
        score -= 0.18

    return score


def _beam_width(total_sentences: int) -> int:
    if total_sentences <= 8:
        return 10
    if total_sentences <= 20:
        return 8
    if total_sentences <= 50:
        return 6
    return 4


def _best_global_order(units: List[SentenceUnit]) -> List[int]:
    units_by_index = {u.index: u for u in units}
    all_indices = [u.index for u in units]
    return _beam_pairwise_order(all_indices, units_by_index)


def _beam_pairwise_order(indices: List[int], units_by_index: Dict[int, SentenceUnit]) -> List[int]:
    total = len(indices)
    if total <= 1:
        return list(indices)

    width = min(_beam_width(total), total)
    start_candidates = sorted(
        indices,
        key=lambda idx: (_start_sentence_score(units_by_index[idx]), -units_by_index[idx].index),
        reverse=True,
    )[:width]

    beam = []
    for idx in start_candidates:
        start_unit = units_by_index[idx]
        counts: Dict[str, int] = {}
        for ent in start_unit.entities:
            counts[ent] = counts.get(ent, 0) + 1
        chain_bonus = _entity_chain_bonus([start_unit])
        start_score = _start_sentence_score(start_unit) + 0.20 * chain_bonus
        beam.append(([idx], {j for j in indices if j != idx}, start_score, counts, chain_bonus))

    for pos in range(1, total):
        expanded = []
        for path, remaining, score, entity_counts, chain_bonus in beam:
            prev = units_by_index[path[-1]]
            ordered_remaining = sorted(
                remaining,
                key=lambda idx: (
                    _temporal_key(units_by_index[idx]),
                    units_by_index[idx].index,
                ),
            )
            for idx in ordered_remaining:
                curr = units_by_index[idx]
                pair = _pair_score(prev, curr)
                next_counts, chain_delta = _chain_bonus_delta(entity_counts, curr)
                next_chain = chain_bonus + chain_delta
                next_score = score + pair + 0.04 * curr.local_score + 0.08 * _position_bias(curr, pos) + 0.20 * chain_delta
                next_path = path + [idx]
                next_remaining = set(remaining)
                next_remaining.remove(idx)
                expanded.append((next_path, next_remaining, next_score, next_counts, next_chain))
        if not expanded:
            break
        expanded.sort(key=lambda item: item[2], reverse=True)
        beam = expanded[:width]

    best_path, _, _, _, _ = max(beam, key=lambda item: item[2])
    return best_path


def _promote_connected_lead(ordered_indices: List[int], units_by_index: Dict[int, SentenceUnit]) -> List[int]:
    if len(ordered_indices) < 3:
        return ordered_indices

    ordered_units = [units_by_index[idx] for idx in ordered_indices]
    connectivity = _topic_connectivity(ordered_units)
    first_idx = ordered_indices[0]
    first_conn = connectivity.get(first_idx, 0.0)

    non_pronoun_candidates = [idx for idx in ordered_indices if not units_by_index[idx].starts_with_pronoun]
    if not non_pronoun_candidates:
        return ordered_indices

    best_idx = max(non_pronoun_candidates, key=lambda idx: connectivity.get(idx, 0.0))
    best_conn = connectivity.get(best_idx, 0.0)
    if best_idx == first_idx:
        return ordered_indices

    # If lead sentence is weakly connected, promote the most connected sentence.
    if first_conn < 0.05 and best_conn >= 0.08:
        reworked = [idx for idx in ordered_indices if idx != best_idx]
        return [best_idx] + reworked
    return ordered_indices


def _avoid_pronoun_lead(ordered_indices: List[int], units_by_index: Dict[int, SentenceUnit]) -> List[int]:
    if len(ordered_indices) < 2:
        return ordered_indices
    first_idx = ordered_indices[0]
    if not units_by_index[first_idx].starts_with_pronoun:
        return ordered_indices

    for idx in ordered_indices[1:]:
        if not units_by_index[idx].starts_with_pronoun:
            reordered = [i for i in ordered_indices if i != idx]
            return [idx] + reordered
    return ordered_indices


def _enforce_pronoun_antecedents(ordered_indices: List[int], units_by_index: Dict[int, SentenceUnit]) -> List[int]:
    if len(ordered_indices) < 3:
        return ordered_indices

    result = list(ordered_indices)
    moved = False
    for idx in list(result):
        curr = units_by_index[idx]
        if not curr.starts_with_pronoun:
            continue

        best_candidate = None
        best_score = 0.0
        for other_idx in result:
            if other_idx == idx:
                continue
            other = units_by_index[other_idx]
            if other.starts_with_pronoun:
                continue
            score = _continuity(other, curr)
            if score > best_score:
                best_score = score
                best_candidate = other_idx

        if best_candidate is None or best_score < 0.03:
            continue

        curr_pos = result.index(idx)
        candidate_pos = result.index(best_candidate)
        target_pos = candidate_pos + 1
        if curr_pos == target_pos:
            continue

        # Force pronoun sentence after its most likely antecedent.
        result.pop(curr_pos)
        if curr_pos < target_pos:
            target_pos -= 1
        result.insert(target_pos, idx)
        moved = True

    if moved:
        return result
    return ordered_indices


def _apply_topic_block_order(ordered_indices: List[int], units_by_index: Dict[int, SentenceUnit]) -> List[int]:
    if len(ordered_indices) < 3:
        return ordered_indices

    explicit_temporal_cues = 0
    for idx in ordered_indices:
        text = units_by_index[idx].text.lower()
        if _starts_with_any(text, START_CUES) or _starts_with_any(text, MIDDLE_CUES) or _starts_with_any(text, END_CUES):
            explicit_temporal_cues += 1
    if explicit_temporal_cues >= 2:
        return ordered_indices

    groups: Dict[str, List[int]] = {}
    for idx in ordered_indices:
        topic = units_by_index[idx].topic
        groups.setdefault(topic, []).append(idx)

    if len(groups) <= 1:
        return ordered_indices

    ordered_topics = sorted(
        groups.keys(),
        key=lambda topic: (_topic_rank(topic), min(units_by_index[idx].index for idx in groups[topic])),
    )

    output: List[int] = []
    for topic in ordered_topics:
        members = groups[topic]
        members = sorted(
            members,
            key=lambda idx: (
                _temporal_key(units_by_index[idx]),
                units_by_index[idx].index,
            ),
        )
        output.extend(members)
    return output


def _order_by_topic_then_pairwise(units: List[SentenceUnit]) -> List[int]:
    if not units:
        return []

    units_by_index = {u.index: u for u in units}
    groups: Dict[str, List[int]] = {}
    for u in units:
        groups.setdefault(u.topic, []).append(u.index)

    ordered_topics = sorted(
        groups.keys(),
        key=lambda topic: (_topic_rank(topic), min(units_by_index[idx].index for idx in groups[topic])),
    )

    output: List[int] = []
    for topic in ordered_topics:
        indices = groups[topic]
        ordered_group = _beam_pairwise_order(indices, units_by_index)
        # Temporal smoothing within same topic.
        ordered_group = sorted(
            ordered_group,
            key=lambda idx: (
                _temporal_key(units_by_index[idx]),
                ordered_group.index(idx),
            ),
        )
        output.extend(ordered_group)
    return output


def parser_reorder(sentences: List[str], nlp) -> Tuple[List[str], float]:
    """Parsing-based reorder with global coherence reranking."""
    if not sentences:
        return [], 0.0
    if len(sentences) == 1:
        return [sentences[0]], 1.0

    docs = _build_docs(sentences, nlp)
    local_raw = []
    for sentence, doc in zip(sentences, docs):
        local_raw.append(_parse_score(doc) + _cue_bonus(sentence))
    local_norm = _normalize(local_raw)

    units: List[SentenceUnit] = []
    for idx, (sentence, doc, score) in enumerate(zip(sentences, docs, local_norm)):
        keywords = _extract_keywords(doc)
        entities = _extract_entities(doc)
        subjects = _extract_subjects(doc)
        units.append(
            SentenceUnit(
                index=idx,
                text=sentence,
                local_score=score,
                keywords=keywords,
                entities=entities,
                subjects=subjects,
                starts_with_pronoun=_starts_with_pronoun(doc),
                stage=_sentence_stage(sentence),
                topic=_classify_topic(sentence, keywords, entities),
            )
        )

    # Reorder gating / independence detection for high topic diversity.
    if _is_independent(units) or not _should_reorder(units):
        confidence = max(0.15, min(0.50, 0.22 + 0.25 * _average_pairwise_continuity(units)))
        return sentences.copy(), round(confidence, 3)

    best_indices = _best_global_order(units)
    units_by_index = {u.index: u for u in units}
    best_indices = _promote_connected_lead(best_indices, units_by_index)
    best_indices = _avoid_pronoun_lead(best_indices, units_by_index)
    best_indices = _enforce_pronoun_antecedents(best_indices, units_by_index)
    ordered = [sentences[idx] for idx in best_indices]

    ordered_units = [units_by_index[idx] for idx in best_indices]
    local_conf = sum(u.local_score for u in ordered_units) / len(ordered_units)

    transitions: List[float] = []
    for pos in range(1, len(ordered_units)):
        transitions.append(_transition_score(ordered_units[pos - 1], ordered_units[pos], pos, len(ordered_units)))
    transition_conf = sum(transitions) / len(transitions) if transitions else local_conf

    confidence = 0.55 * local_conf + 0.45 * transition_conf
    confidence = max(0.0, min(1.0, confidence))
    return ordered, round(confidence, 3)
