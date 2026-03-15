def main() -> None:
    import os
    from pathlib import Path

    base_dir = Path(__file__).resolve().parent
    stanza_dir = base_dir / ".stanza"
    nltk_dir = base_dir / ".nltk_data"
    stanza_dir.mkdir(parents=True, exist_ok=True)
    nltk_dir.mkdir(parents=True, exist_ok=True)

    os.environ["STANZA_RESOURCES_DIR"] = str(stanza_dir)
    os.environ["NLTK_DATA"] = str(nltk_dir)

    import stanza
    import nltk

    stanza.download("en")
    nltk.download("reuters")
    nltk.download("punkt")


if __name__ == "__main__":
    main()
