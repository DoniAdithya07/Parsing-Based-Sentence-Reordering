from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

from baseline import baseline_reorder
from data_loader import ensure_nltk_data, load_reuters_sentences
from parser_model import get_spacy_model, parser_reorder
from preprocess import clean_and_split_sentences, format_output

st.set_page_config(
    page_title="Parsing-Based Sentence Reordering",
    page_icon="🧠",
    layout="wide",
)


@st.cache_resource
def get_nlp_cached():
    return get_spacy_model()


@st.cache_data(show_spinner=False)
def get_reuters_samples(limit: int = 400) -> List[str]:
    return load_reuters_sentences(limit=limit)


def to_percent(score: float | None) -> int | None:
    if score is None:
        return None
    bounded = max(0.0, min(1.0, float(score)))
    return int(round(bounded * 100))


def extract_parse_cards(sentences: List[str]) -> List[Dict[str, str]]:
    if not sentences:
        return []

    nlp = get_nlp_cached()
    cards: List[Dict[str, str]] = []
    for sentence in sentences[:3]:
        doc = nlp(sentence)
        subject = next((t.text for t in doc if t.dep_ in {"nsubj", "nsubjpass"}), "-")
        root = next((t.text for t in doc if t.dep_ == "ROOT"), "-")
        obj = next((t.text for t in doc if t.dep_ in {"dobj", "obj", "iobj", "pobj"}), "-")
        cards.append({"sentence": sentence, "subject": subject, "verb": root, "object": obj})
    return cards


def build_reorder_result(sentences: List[str], selected_method: str) -> Dict[str, Any]:
    baseline_output: List[str] = []
    parsing_output: List[str] = []
    baseline_score: float | None = None
    parsing_score: float | None = None
    parser_error = ""
    parser_fallback = False

    method = selected_method.lower().strip()
    if method == "baseline":
        baseline_output, baseline_score = baseline_reorder(sentences)
    elif method == "parser":
        try:
            parsing_output, parsing_score = parser_reorder(sentences, get_nlp_cached())
        except RuntimeError as exc:
            parser_error = str(exc)
            parsing_output, parsing_score = baseline_reorder(sentences)
            parser_fallback = True
    else:
        baseline_output, baseline_score = baseline_reorder(sentences)
        try:
            parsing_output, parsing_score = parser_reorder(sentences, get_nlp_cached())
        except RuntimeError as exc:
            parser_error = str(exc)
            parsing_output = baseline_output.copy()
            parsing_score = baseline_score
            parser_fallback = True
        method = "compare"

    return {
        "selected_method": method,
        "baseline_output": baseline_output,
        "parsing_output": parsing_output,
        "baseline_score": baseline_score,
        "parsing_score": parsing_score,
        "baseline_percent": to_percent(baseline_score),
        "parsing_percent": to_percent(parsing_score),
        "parser_error": parser_error,
        "parser_fallback": parser_fallback,
    }


def validate_input(raw_input: str, min_sentences: int = 3, max_sentences: int = 30):
    if not raw_input or not raw_input.strip():
        return [], "Input is empty"

    sentences = clean_and_split_sentences(raw_input)
    if len(sentences) < min_sentences:
        return [], f"Too few sentences. Please enter at least {min_sentences} sentences."
    if len(sentences) > max_sentences:
        return [], f"Input is too large. Please keep it within {max_sentences} sentences."
    return sentences, ""


def append_history(method: str, input_text: str, result: Dict[str, Any]) -> None:
    st.session_state.history.insert(
        0,
        {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "method": method,
            "input_text": input_text,
            "baseline_text": format_output(result["baseline_output"]),
            "parsing_text": format_output(result["parsing_output"]),
            "baseline_percent": result["baseline_percent"],
            "parsing_percent": result["parsing_percent"],
        },
    )


if "input_text" not in st.session_state:
    st.session_state.input_text = ""
if "history" not in st.session_state:
    st.session_state.history = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "last_method" not in st.session_state:
    st.session_state.last_method = "compare"

st.title("Parsing-Based Sentence Reordering")
st.caption("Streamlit version for deployment and demo")

try:
    ensure_nltk_data(allow_punkt_download=False)
except Exception:
    # Keep app usable even if environment blocks NLTK setup.
    pass

reorder_tab, dataset_tab, about_tab = st.tabs(["Reorder", "Dataset", "About & Paper"])

with reorder_tab:
    st.subheader("Run Reordering")
    st.write("Paste at least 3 sentences, then compare baseline and parsing-based outputs.")

    st.text_area(
        "Input text",
        key="input_text",
        height=180,
        placeholder="Sentence 1\nSentence 2\nSentence 3\nor paste a paragraph...",
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    run_baseline = c1.button("Run Baseline", use_container_width=True)
    run_parser = c2.button("Run Parsing", use_container_width=True)
    run_compare = c3.button("Compare Both", use_container_width=True)
    load_sample = c4.button("Load Sample", use_container_width=True)
    clear_input = c5.button("Clear", use_container_width=True)

    if load_sample:
        samples = get_reuters_samples(limit=400)
        if len(samples) >= 3:
            picked = random.sample(samples, k=random.randint(3, 5))
            st.session_state.input_text = "\n".join(picked)
            st.rerun()
        else:
            st.error("Reuters samples are unavailable in this environment.")

    if clear_input:
        st.session_state.input_text = ""
        st.session_state.last_result = None
        st.rerun()

    run_method = None
    if run_baseline:
        run_method = "baseline"
    elif run_parser:
        run_method = "parser"
    elif run_compare:
        run_method = "compare"

    if run_method:
        sentences, validation_error = validate_input(st.session_state.input_text)
        if validation_error:
            st.error(validation_error)
        else:
            result = build_reorder_result(sentences, run_method)
            st.session_state.last_method = run_method
            st.session_state.last_result = result
            append_history(run_method, st.session_state.input_text, result)

    result = st.session_state.last_result
    if result:
        if result["parser_error"]:
            st.warning(f"{result['parser_error']} Using fallback output for parsing view.")

        left, right = st.columns(2)
        with left:
            st.markdown("### Baseline Output")
            st.text_area(
                "baseline_output",
                value=format_output(result["baseline_output"]),
                height=220,
                disabled=True,
                label_visibility="collapsed",
            )
            if result["baseline_percent"] is not None:
                st.metric("Baseline Score", f"{result['baseline_percent']}%")

        with right:
            st.markdown("### Parsing-Based Output")
            st.text_area(
                "parsing_output",
                value=format_output(result["parsing_output"]),
                height=220,
                disabled=True,
                label_visibility="collapsed",
            )
            if result["parsing_percent"] is not None:
                st.metric("Parsing Score", f"{result['parsing_percent']}%")

        st.markdown("### Parsing Logic Preview")
        preview_source = result["parsing_output"] or result["baseline_output"]
        cards = extract_parse_cards(preview_source)
        cols = st.columns(min(3, len(cards)) or 1)
        for idx, item in enumerate(cards):
            with cols[idx % len(cols)]:
                st.markdown(
                    f"**Sentence**: {item['sentence']}  \n"
                    f"**Subject**: {item['subject']}  \n"
                    f"**Verb**: {item['verb']}  \n"
                    f"**Object**: {item['object']}"
                )

    with st.expander("Run History (Current Session)", expanded=False):
        if not st.session_state.history:
            st.info("No runs yet in this session.")
        else:
            for i, item in enumerate(st.session_state.history[:10], start=1):
                st.markdown(
                    f"**{i}. {item['ts']}** | method: `{item['method']}` | "
                    f"baseline: `{item['baseline_percent']}%` | parsing: `{item['parsing_percent']}%`"
                )

with dataset_tab:
    st.subheader("Dataset Summary")
    st.markdown(
        """
- Dataset: **Reuters-21578** (used via NLTK subset in this project)
- Total documents used here: **10,788**
- Categories/topics: **90**
- Standard split:
  - Training: **7,769**
  - Test: **3,019**
        """
    )

    with st.expander("Preview sample sentences"):
        samples = get_reuters_samples(limit=20)
        if not samples:
            st.warning("No Reuters samples available.")
        else:
            for idx, sent in enumerate(samples[:10], start=1):
                st.write(f"{idx}. {sent}")

with about_tab:
    st.subheader("Research Inspiration")
    st.markdown(
        """
This project is inspired by:

**Mirella Lapata (2003)**  
*Probabilistic Text Structuring: Experiments with Sentence Ordering* (ACL 2003)

- [ACL Anthology Page](https://aclanthology.org/P03-1069/)
        """
    )

    pdf_path = Path("static/papers/P03-1069.pdf")
    if pdf_path.exists():
        with pdf_path.open("rb") as fh:
            st.download_button(
                label="Download Paper PDF (Local Copy)",
                data=fh.read(),
                file_name="P03-1069.pdf",
                mime="application/pdf",
            )

    st.subheader("Why this model is better for this project")
    st.dataframe(
        {
            "Criterion": [
                "Explainability",
                "Reproducibility",
                "Cost Efficiency",
                "Data Privacy (Local)",
                "General Raw Accuracy",
            ],
            "Our Model": ["High", "High", "High", "High", "Medium"],
            "Typical Market Model": ["Low/Medium", "Medium", "Low/Medium", "Medium", "High"],
        },
        hide_index=True,
        use_container_width=True,
    )

    st.caption("This is a qualitative comparison for academic/demo use, not a benchmark leaderboard.")
