from __future__ import annotations

from pathlib import Path

import nltk
import stanza
import re
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
NLTK_DATA_DIR = PROJECT_ROOT / ".nltk_data"
STANZA_RESOURCES_DIR = PROJECT_ROOT / ".stanza"

# Download required resources at startup (for cloud environments).
stanza.download("en", dir=str(STANZA_RESOURCES_DIR))
nltk.download("punkt", download_dir=str(NLTK_DATA_DIR))
nltk.download("reuters", download_dir=str(NLTK_DATA_DIR))


def configure_resources() -> None:
    nltk.data.path.insert(0, str(NLTK_DATA_DIR))


def ensure_nltk_resource(resource_path: str, package: str) -> None:
    try:
        nltk.data.find(resource_path)
    except LookupError:
        nltk.download(package, download_dir=str(NLTK_DATA_DIR), quiet=True)


def init_stanza_pipeline() -> stanza.Pipeline:
    return stanza.Pipeline(
        "en",
        dir=str(STANZA_RESOURCES_DIR),
        processors="tokenize,pos,lemma,depparse",
        tokenize_no_ssplit=True,
        download_method=stanza.DownloadMethod.REUSE_RESOURCES,
        verbose=False,
    )


def first_clean_reuters_sentence() -> str:
    from nltk.corpus import reuters

    sentence_tokenizer = nltk.data.load("tokenizers/punkt/english.pickle")
    def looks_like_headline(text: str) -> bool:
        letters = [ch for ch in text if ch.isalpha()]
        if not letters:
            return True
        lower = sum(ch.islower() for ch in letters)
        upper = sum(ch.isupper() for ch in letters)
        if lower == 0 and upper > 0:
            return True
        return upper / max(1, (upper + lower)) > 0.85 and len(text) < 140

    def strip_headline_lines(text: str) -> str:
        lines = text.splitlines()
        body_start = 0
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            if looks_like_headline(line.strip()):
                body_start = i + 1
                continue
            break
        return "\n".join(lines[body_start:])

    for file_id in reuters.fileids():
        raw = reuters.raw(file_id)
        raw_body = strip_headline_lines(raw)
        for idx, sent in enumerate(sentence_tokenizer.tokenize(raw_body)):
            clean = " ".join(sent.split())
            if not any(ch.isalpha() for ch in clean):
                continue
            if looks_like_headline(clean):
                continue
            if len(clean.split()) < 6:
                continue
            return clean
    raise RuntimeError("No valid sentence found in Reuters corpus.")


def reorder_sentence(sentence: str, nlp: stanza.Pipeline, order: str) -> str:
    doc = nlp(sentence)
    if not doc.sentences:
        return sentence

    words = doc.sentences[0].words
    children: dict[int, list[int]] = {}
    for w in words:
        children.setdefault(w.head, []).append(w.id)

    def subtree_ids(head_id: int) -> set[int]:
        stack = [head_id]
        seen: set[int] = set()
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(children.get(cur, []))
        return seen

    def is_finite_verb(w: stanza.models.common.doc.Word) -> bool:
        if w.upos != "VERB":
            return False
        if w.feats is None:
            return True
        if "VerbForm=Fin" in w.feats:
            return True
        return any(
            child_id
            for child_id in children.get(w.id, [])
            if next((c for c in words if c.id == child_id and c.deprel.startswith("aux")), None)
        )

    def clause_size(head: stanza.models.common.doc.Word) -> int:
        return len(subtree_ids(head.id))

    clause_heads = [
        w
        for w in words
        if is_finite_verb(w) and (w.deprel in {"root", "ccomp", "xcomp", "advcl", "acl"} or w.head == 0)
    ]
    root = next((w for w in words if w.head == 0), None)
    reporting_verbs = {"say", "report", "state", "tell", "add"}

    target_root = None
    if root and root.lemma and root.lemma.lower() in reporting_verbs:
        ccomp = next(
            (w for w in words if w.head == root.id and w.deprel == "ccomp" and is_finite_verb(w)),
            None,
        )
        if ccomp:
            ccomp_ids = subtree_ids(ccomp.id)
            ccomp_candidates = [w for w in clause_heads if w.id in ccomp_ids]
            if ccomp_candidates:
                target_root = max(ccomp_candidates, key=clause_size)
            else:
                target_root = ccomp

    if not target_root:
        non_reporting = [
            w for w in clause_heads if not (w.lemma and w.lemma.lower() in reporting_verbs)
        ]
        pool = non_reporting if non_reporting else clause_heads
        if pool:
            target_root = max(pool, key=clause_size)
        else:
            target_root = root

    verb = target_root if target_root and target_root.upos == "VERB" else None
    subj = next(
        (
            w
            for w in words
            if w.head == (target_root.id if target_root else -1) and w.deprel.startswith("nsubj")
        ),
        None,
    )
    obj = next(
        (
            w
            for w in words
            if w.head == (target_root.id if target_root else -1) and w.deprel in {"obj", "iobj", "ccomp"}
        ),
        None,
    )

    if not (subj and verb and obj):
        return sentence

    target_ids = subtree_ids(target_root.id) if target_root else set()

    def phrase_within_target(head_id: int) -> str:
        ids = subtree_ids(head_id).intersection(target_ids) if target_ids else subtree_ids(head_id)
        ordered = [w.text for w in words if w.id in ids]
        return " ".join(ordered)

    subj_phrase = phrase_within_target(subj.id)
    obj_phrase = phrase_within_target(obj.id)
    if order == "VSO (Verb-Subject-Object)":
        reordered = f"{verb.text} {subj_phrase} {obj_phrase}"
    else:
        reordered = f"{subj_phrase} {obj_phrase} {verb.text}"
    if sentence.rstrip().endswith((".", "!", "?")):
        reordered = reordered + sentence.rstrip()[-1]
    return clean_spacing(reordered)


def clean_spacing(text: str) -> str:
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"\s+'s\b", "'s", text)
    text = re.sub(r"\s*-\s*", "-", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def initialize() -> stanza.Pipeline:
    configure_resources()
    ensure_nltk_resource("corpora/reuters", "reuters")
    ensure_nltk_resource("tokenizers/punkt", "punkt")
    ensure_nltk_resource("tokenizers/punkt_tab/english", "punkt_tab")
    return init_stanza_pipeline()


PIPELINE = initialize()


def order_label(order: str) -> str:
    if order.startswith("VSO"):
        return "VSO Output"
    return "SOV Output"


def order_explanation(order: str) -> str:
    if order.startswith("VSO"):
        return "Verb-Subject-Object (VSO): verb first, then subject, then object."
    return "Subject-Object-Verb (SOV): subject first, then object, then verb."


def order_ui_update(order: str) -> tuple[str, dict]:
    return order_explanation(order), {"label": order_label(order)}


def status_line(order: str) -> str:
    return f"Model: Stanza English UD | Target Order: {order}"


def process_sentence(order: str) -> tuple[str, str, dict, str, str]:
    sentence = first_clean_reuters_sentence()
    reordered = reorder_sentence(sentence, PIPELINE, order)
    return (
        sentence,
        reordered,
        {"label": order_label(order)},
        order_explanation(order),
        status_line(order),
    )


def main() -> None:
    st.title("Parsing-Based Sentence Reordering")

    order_choice = st.selectbox(
        "Target Structure",
        ["SOV (Subject-Object-Verb)", "VSO (Verb-Subject-Object)"],
        index=0,
    )

    st.caption(order_explanation(order_choice))

    if st.button("Fetch & Process"):
        sentence, reordered, _, _, _ = process_sentence(order_choice)
        st.session_state["original"] = sentence
        st.session_state["reordered"] = reordered
        st.session_state["status"] = status_line(order_choice)

    original_value = st.session_state.get("original", "")
    reordered_value = st.session_state.get("reordered", "")
    status_value = st.session_state.get("status", status_line(order_choice))

    st.text_area("Original Sentence", value=original_value, height=150)
    st.text_area(order_label(order_choice), value=reordered_value, height=150)
    st.caption(status_value)


if __name__ == "__main__":
    main()
