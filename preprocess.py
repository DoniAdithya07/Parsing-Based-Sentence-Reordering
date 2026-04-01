from __future__ import annotations

from typing import List

from nltk.tokenize import sent_tokenize


def clean_and_split_sentences(raw_text: str) -> List[str]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    sentences: List[str] = []

    # If user already gave sentence-per-line input, keep that structure.
    if len(lines) >= 3:
        for line in lines:
            if line[:2].isdigit() and line[2:3] in {".", ")"}:
                line = line[3:].strip()
            cleaned = " ".join(line.split())
            if cleaned:
                sentences.append(cleaned)
        return sentences

    # Otherwise, treat input as paragraph(s) and split into sentences.
    for sent in sent_tokenize(raw_text):
        cleaned = " ".join(sent.split())
        if cleaned:
            sentences.append(cleaned)
    return sentences


def format_output(sentences: List[str]) -> str:
    return "\n".join(sentences)
