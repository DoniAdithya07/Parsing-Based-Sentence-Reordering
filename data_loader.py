from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

import nltk

PROJECT_ROOT = Path(__file__).resolve().parent
NLTK_DATA_DIR = PROJECT_ROOT / ".nltk_data"


def _ensure_resource(resource_path: str, package_name: str, allow_download: bool = True) -> None:
    try:
        nltk.data.find(resource_path)
        return
    except LookupError:
        pass

    if not allow_download:
        return

    # Keep startup resilient in offline/restricted environments.
    nltk.download(package_name, download_dir=str(NLTK_DATA_DIR), quiet=True)


@lru_cache(maxsize=4)
def ensure_nltk_data(
    include_reuters: bool = False,
    allow_punkt_download: bool = True,
    allow_reuters_download: bool = False,
) -> None:
    """Ensure required NLTK resources are available."""
    nltk_data_dir = str(NLTK_DATA_DIR)
    if nltk_data_dir not in nltk.data.path:
        nltk.data.path.insert(0, nltk_data_dir)

    _ensure_resource("tokenizers/punkt", "punkt", allow_download=allow_punkt_download)

    if include_reuters:
        _ensure_resource("corpora/reuters", "reuters", allow_download=allow_reuters_download)


def load_reuters_sentences(limit: int = 200) -> List[str]:
    """Load a small list of clean sentences from Reuters for examples."""
    ensure_nltk_data(include_reuters=True, allow_punkt_download=False, allow_reuters_download=False)
    from nltk.corpus import reuters
    from nltk.tokenize import sent_tokenize

    sentences: List[str] = []
    try:
        file_ids = reuters.fileids()
    except LookupError:
        return sentences

    for file_id in file_ids:
        raw = reuters.raw(file_id)
        for sent in sent_tokenize(raw):
            cleaned = " ".join(sent.split())
            if cleaned and len(cleaned.split()) >= 6:
                sentences.append(cleaned)
                if len(sentences) >= limit:
                    return sentences
    return sentences
