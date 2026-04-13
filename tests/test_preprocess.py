from preprocess import clean_and_split_sentences


def test_split_sentence_per_line_with_numbering():
    raw = "1) First sentence.\n2) Next sentence.\n3) Final sentence."
    sentences = clean_and_split_sentences(raw)

    assert len(sentences) == 3
    assert sentences[0] == "First sentence."
    assert sentences[1] == "Next sentence."
    assert sentences[2] == "Final sentence."


def test_split_multilingual_punctuation_text():
    raw = (
        "\u092f\u0939 \u092a\u0939\u0932\u093e \u0935\u093e\u0915\u094d\u092f \u0939\u0948\u0964 "
        "\u092f\u0939 \u0926\u0942\u0938\u0930\u093e \u0935\u093e\u0915\u094d\u092f \u0939\u0948\u0964 "
        "\u092f\u0939 \u0924\u0940\u0938\u0930\u093e \u0935\u093e\u0915\u094d\u092f \u0939\u0948\u0964"
    )
    sentences = clean_and_split_sentences(raw)

    assert len(sentences) == 3


def test_split_noisy_semicolon_blocks():
    raw = "alpha beta gamma; delta epsilon zeta; eta theta iota"
    sentences = clean_and_split_sentences(raw)

    assert len(sentences) == 3


def test_merge_fragmented_lines_before_reorder():
    raw = (
        "The talks broke down last June after\n"
        "the two sides said they could not agree on the terms of the sale.\n"
        "No decisions are likely until after Indonesia's elections on April 23, traders said.\n"
        "A final review is expected next week."
    )
    sentences = clean_and_split_sentences(raw)

    assert len(sentences) == 3
    assert sentences[0].startswith("The talks broke down last June after the two sides said")


def test_merge_headline_with_following_body_line():
    raw = (
        "JAPAN GIVEN LITTLE HOPE OF AVOIDING U.S. SANCTIONS\n"
        "A top U.S. official said Japan has little chance of persuading the U.S. to drop threatened trade sanctions.\n"
        "No decisions are likely until after Indonesia's elections on April 23.\n"
        "Traders are waiting for clarity."
    )
    sentences = clean_and_split_sentences(raw)

    assert len(sentences) >= 3
    assert "JAPAN GIVEN LITTLE HOPE OF AVOIDING U.S. SANCTIONS" in sentences[0]
    assert "A top U.S. official said Japan has little chance" in sentences[1] or "A top U.S. official said Japan has little chance" in sentences[0]


def test_clean_malformed_entity_tokens():
    raw = (
        "The Hong Kong Economic Journal quoted a spokesman saying &lt Barwon Farmlands Ltd> was planning a branch.\n"
        "The talks broke down last June.\n"
        "No decisions are likely until after elections."
    )
    sentences = clean_and_split_sentences(raw)

    assert any("Barwon Farmlands Ltd" in s for s in sentences)
    assert all("<" not in s and ">" not in s and "&lt" not in s for s in sentences)
