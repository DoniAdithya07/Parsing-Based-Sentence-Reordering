import spacy

from parser_model import parser_reorder


def test_parser_reorder_preserves_all_sentences():
    nlp = spacy.blank("en")
    sentences = [
        "The device was assembled in the lab.",
        "Engineers then calibrated the sensors.",
        "Finally, the quality team approved the release.",
        "A final report was shared with stakeholders.",
    ]

    ordered, confidence = parser_reorder(sentences, nlp)

    assert sorted(ordered) == sorted(sentences)
    assert 0.0 <= confidence <= 1.0


def test_parser_reorder_prefers_simple_temporal_progression():
    nlp = spacy.blank("en")
    first = "First, the team collected the raw data."
    middle = "Then, they cleaned the dataset and removed duplicates."
    end = "Finally, they published the final analysis."

    ordered, _ = parser_reorder([end, middle, first], nlp)
    positions = {sentence: idx for idx, sentence in enumerate(ordered)}

    assert positions[first] < positions[middle] < positions[end]


def test_parser_reorder_keeps_pronoun_sentence_with_its_topic_cluster():
    nlp = spacy.blank("en")
    asian = (
        "ASIAN EXPORTERS FEAR DAMAGE FROM U.S.-JAPAN RIFT Mounting trade friction between the U.S. and Japan "
        "has raised fears among many of Asia's exporting nations."
    )
    pronoun_followup = (
        "They told Reuter correspondents in Asian capitals a U.S. move against Japan might boost protectionist "
        "sentiment in the U.S."
    )
    coffee = "Trading in coffee in calendar 1986 amounted to only 1,905 tonnes."
    rubber = "Rubber contracts are traded FOB, up to five months forward."
    san_miguel = (
        "SAN MIGUEL DEAL HIT BY MORE LAWSUITS A bid by San Miguel Corp to buy back sequestered shares "
        "has been hit by two new lawsuits."
    )

    ordered, _ = parser_reorder([asian, coffee, pronoun_followup, rubber, san_miguel], nlp)
    positions = {sentence: idx for idx, sentence in enumerate(ordered)}

    assert positions[pronoun_followup] > positions[asian]
    assert abs(positions[pronoun_followup] - positions[asian]) <= 1


def test_parser_reorder_keeps_topic_blocks_in_stable_order():
    nlp = spacy.blank("en")
    asian = (
        "ASIAN EXPORTERS FEAR DAMAGE FROM U.S.-JAPAN RIFT Mounting trade friction between the U.S. and Japan "
        "has raised fears among many of Asia's exporting nations."
    )
    pronoun_followup = (
        "They told Reuter correspondents in Asian capitals a U.S. move against Japan might boost protectionist "
        "sentiment in the U.S."
    )
    coffee = "Trading in coffee in calendar 1986 amounted to only 1,905 tonnes in 381 lots."
    rubber = "Rubber contracts are traded FOB, up to five months forward."
    san_miguel = (
        "SAN MIGUEL DEAL HIT BY MORE LAWSUITS A bid by San Miguel Corp to buy back 38.1 mln sequestered shares "
        "has been hit by two new lawsuits."
    )

    ordered, _ = parser_reorder([asian, coffee, pronoun_followup, rubber, san_miguel], nlp)
    positions = {sentence: idx for idx, sentence in enumerate(ordered)}

    assert positions[asian] < positions[san_miguel]
    assert positions[pronoun_followup] > positions[asian]
    assert positions[coffee] < positions[san_miguel]
    assert positions[rubber] < positions[san_miguel]


def test_parser_reorder_handles_disconnected_multi_topic_batches():
    nlp = spacy.blank("en")
    sentences = [
        "Kuwait discussed oil export risk near the Gulf.",
        "Coffee trading in 1986 reached 1,905 tonnes in 381 lots.",
        "A Philippine lawsuit challenged a food and brewery share deal.",
    ]

    ordered, confidence = parser_reorder(sentences, nlp)
    assert sorted(ordered) == sorted(sentences)
    positions = {sentence: idx for idx, sentence in enumerate(ordered)}
    assert positions["A Philippine lawsuit challenged a food and brewery share deal."] == 2
    assert 0.0 <= confidence <= 1.0


def test_parser_reorder_skips_when_topic_diversity_is_high():
    nlp = spacy.blank("en")
    policy = "A top U.S. official said new sanctions may be imposed after elections."
    economy = "Trading in coffee in 1986 reached 1,905 tonnes in 381 lots."
    legal = "A new lawsuit was filed in court against the bank."
    corporate = "San Miguel Corp announced a bid to buy additional shares."
    technical = "Engineers tuned the software pipeline and improved model latency."

    original = [technical, corporate, legal, economy, policy]
    ordered, _ = parser_reorder(original, nlp)

    assert ordered == original


def test_parser_reorder_soft_topic_scoring_keeps_related_sentences_close():
    nlp = spacy.blank("en")
    policy_a = "A top U.S. official said sanctions may be expanded."
    policy_b = "The government said new trade curbs are under review."
    economy = "Coffee exports fell and traders reported lower market demand."
    legal = "A lawsuit was filed in court against the bank."

    ordered, _ = parser_reorder([economy, policy_b, legal, policy_a], nlp)
    positions = {sentence: idx for idx, sentence in enumerate(ordered)}

    assert abs(positions[policy_a] - positions[policy_b]) <= 1
