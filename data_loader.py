from __future__ import annotations

from pathlib import Path
from typing import List

import nltk

PROJECT_ROOT = Path(__file__).resolve().parent
NLTK_DATA_DIR = PROJECT_ROOT / ".nltk_data"


def ensure_nltk_data() -> None:
    """Ensure required NLTK resources are available."""
    nltk.data.path.insert(0, str(NLTK_DATA_DIR))
    try:
        nltk.data.find("corpora/reuters")
    except LookupError:
        nltk.download("reuters", download_dir=str(NLTK_DATA_DIR))
    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        nltk.download("punkt", download_dir=str(NLTK_DATA_DIR))


def load_reuters_sentences(limit: int = 200) -> List[str]:
    """Load a small list of clean sentences from Reuters for examples."""
    ensure_nltk_data()
    from nltk.corpus import reuters
    from nltk.tokenize import sent_tokenize

    sentences: List[str] = []
    for file_id in reuters.fileids():
        raw = reuters.raw(file_id)
        for sent in sent_tokenize(raw):
            cleaned = " ".join(sent.split())
            if cleaned and len(cleaned.split()) >= 6:
                sentences.append(cleaned)
                if len(sentences) >= limit:
                    return sentences
    return sentences
