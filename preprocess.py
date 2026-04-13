from __future__ import annotations

import re
from typing import List

from nltk.tokenize import sent_tokenize


LIST_PREFIX_RE = re.compile(r"^\s*(?:\(?\d{1,3}[\)\.]|[a-zA-Z][\)\.]|[-*\u2022])\s+")
MULTI_PUNCT_SPLIT_RE = re.compile(r"(?<=[.!?\u0964\uFF01\uFF1F])\s+")
SENTENCE_END_RE = re.compile(r"[.!?\u0964\uFF01\uFF1F]\s*$")
MALFORMED_TOKEN_RE = re.compile(r"&lt;?|&gt;?")
SPACED_TAG_RE = re.compile(r"<\s*([^>]+?)\s*>")
ABBREVIATION_RE = re.compile(r"\b(?:[A-Za-z]\.){2,}")
DOT_MARKER = "__DOT__"
CONTINUATION_STARTS = {
    "and",
    "but",
    "or",
    "so",
    "yet",
    "because",
    "despite",
    "after",
    "before",
    "while",
    "when",
    "although",
    "though",
    "if",
    "until",
    "since",
}


def _strip_list_prefix(text: str) -> str:
    return LIST_PREFIX_RE.sub("", text).strip()


def _clean_malformed_tokens(text: str) -> str:
    text = MALFORMED_TOKEN_RE.sub("", text)
    text = SPACED_TAG_RE.sub(r"\1", text)
    text = text.replace("<", "").replace(">", "")
    return text


def _normalize_sentence(text: str) -> str:
    text = _strip_list_prefix(text)
    text = _clean_malformed_tokens(text)
    text = text.strip(" \t\r\n\"'`")
    text = " ".join(text.split())
    return text


def _regex_sentence_split(text: str) -> List[str]:
    text = text.strip()
    if not text:
        return []

    protected = ABBREVIATION_RE.sub(lambda m: m.group(0).replace(".", DOT_MARKER), text)
    parts = [p.strip().replace(DOT_MARKER, ".") for p in MULTI_PUNCT_SPLIT_RE.split(protected) if p.strip()]
    if len(parts) <= 1 and ";" in text:
        parts = [p.strip() for p in text.split(";") if p.strip()]
    return parts or [text]


def _is_all_caps_headline(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    words = [w for w in re.findall(r"[A-Za-z]+", stripped) if w]
    if len(words) < 4 or len(words) > 25:
        return False
    uppercase_words = sum(1 for w in words if w.upper() == w)
    return (uppercase_words / len(words)) >= 0.8


def _starts_continuation(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False

    first_alpha = re.search(r"[A-Za-z]", stripped)
    if not first_alpha:
        return False

    idx = first_alpha.start()
    char = stripped[idx]
    if char.islower():
        return True

    first_word = re.match(r"[A-Za-z]+", stripped[idx:])
    if first_word and first_word.group(0).lower() in CONTINUATION_STARTS:
        return True
    return False


def _is_sentence_end(text: str) -> bool:
    return bool(SENTENCE_END_RE.search(text))


def _merge_fragment_lines(lines: List[str]) -> List[str]:
    if not lines:
        return []

    merged: List[str] = []
    buffer = _normalize_sentence(lines[0])

    for raw_line in lines[1:]:
        line = _normalize_sentence(raw_line)
        if not line:
            continue

        if not buffer:
            buffer = line
            continue

        should_merge = False
        separator = " "

        if _is_all_caps_headline(buffer):
            should_merge = True
            if not _is_sentence_end(buffer):
                separator = ". "
        elif not _is_sentence_end(buffer):
            should_merge = True
        elif _starts_continuation(line):
            should_merge = True
        elif buffer.endswith((",", ";", ":", "-", "—")):
            should_merge = True

        if should_merge:
            buffer = f"{buffer}{separator}{line}".strip()
        else:
            merged.append(buffer)
            buffer = line

    if buffer:
        merged.append(buffer)
    return merged


def _should_preserve_short_line_input(lines: List[str]) -> bool:
    if len(lines) < 3:
        return False

    normalized = [_normalize_sentence(line) for line in lines if _normalize_sentence(line)]
    if len(normalized) < 3:
        return False

    if any(_is_sentence_end(line) for line in normalized):
        return False

    return all(len(line.split()) <= 6 for line in normalized)


def _is_sentence_per_line_input(lines: List[str]) -> bool:
    if len(lines) < 3:
        return False

    sentence_like = 0
    for line in lines:
        if _is_sentence_end(line):
            sentence_like += 1
        elif len(line.split()) <= 18:
            sentence_like += 1

    return (sentence_like / len(lines)) >= 0.6


def clean_and_split_sentences(raw_text: str) -> List[str]:
    raw_text = str(raw_text or "")
    raw_lines = [line.strip() for line in raw_text.replace("\r\n", "\n").splitlines() if line.strip()]
    if _should_preserve_short_line_input(raw_lines):
        lines = [_normalize_sentence(line) for line in raw_lines if _normalize_sentence(line)]
    else:
        lines = _merge_fragment_lines(raw_lines)
    sentences: List[str] = []

    # If user gave sentence-per-line style input, preserve that structure.
    if _is_sentence_per_line_input(lines):
        for line in lines:
            for piece in _regex_sentence_split(line):
                cleaned = _normalize_sentence(piece)
                if cleaned:
                    sentences.append(cleaned)
        return sentences

    # Otherwise, treat input as paragraph(s) and split into sentences.
    merged_text = "\n".join(lines) if lines else raw_text
    try:
        tokenized = sent_tokenize(merged_text)
    except LookupError:
        tokenized = _regex_sentence_split(merged_text)

    if len(tokenized) < 3:
        # Fallback for noisy/unpunctuated text blocks.
        tokenized = _regex_sentence_split(merged_text.replace("\n", " ; "))

    for sent in tokenized:
        cleaned = _normalize_sentence(sent)
        if cleaned:
            sentences.append(cleaned)
    return sentences


def format_output(sentences: List[str]) -> str:
    return "\n".join(sentences)
