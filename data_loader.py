from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List
import re

import nltk

PROJECT_ROOT = Path(__file__).resolve().parent
NLTK_DATA_DIR = PROJECT_ROOT / ".nltk_data"
LOCAL_REUTERS_FALLBACK = PROJECT_ROOT / "dataset" / "reuters_sentences_6plus.txt"


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

    def _local_fallback() -> List[str]:
        if not LOCAL_REUTERS_FALLBACK.exists():
            return []
        out: List[str] = []
        with LOCAL_REUTERS_FALLBACK.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                cleaned = " ".join(line.split())
                if cleaned and len(cleaned.split()) >= 6:
                    out.append(cleaned)
                    if len(out) >= limit:
                        break
        return out

    try:
        file_ids = reuters.fileids()
    except LookupError:
        return _local_fallback()

    for file_id in file_ids:
        raw = reuters.raw(file_id)
        try:
            tokenized = sent_tokenize(raw)
        except LookupError:
            # Fallback for environments where punkt is unavailable.
            tokenized = re.split(r"(?<=[.!?])\s+", raw.strip())
        for sent in tokenized:
            cleaned = " ".join(sent.split())
            if cleaned and len(cleaned.split()) >= 6:
                sentences.append(cleaned)
                if len(sentences) >= limit:
                    return sentences
    return sentences or _local_fallback()
