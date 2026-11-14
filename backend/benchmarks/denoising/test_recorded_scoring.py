"""WER accounting must not turn lost speech or numeric changes into successes."""

import pytest

from benchmarks.denoising.transcribe import error_counts, words


def test_word_errors_include_deleted_speech_and_insertions():
    missing = error_counts("Please visit counter seven now", "Please visit")
    assert missing["deletions"] == 3
    assert missing["errors"] == 3
    assert missing["wer"] == 0.6
    extra = error_counts("counter seven", "counter seven counter seven")
    assert extra["insertions"] == 2
    assert extra["wer"] == 1


def test_normalization_does_not_rewrite_numbers_or_words():
    assert words("DON’T stop, please!") == ["don't", "stop", "please"]
    score = error_counts("counter seven", "Counter 7.")
    assert score["substitutions"] == 1
    assert score["wer"] == 0.5


def test_indic_combining_marks_remain_part_of_words():
    assert words("நேச்சுரலி கர்லி.") == ["நேச்சுரலி", "கர்லி"]
    assert words("कीट ही कोड।") == ["कीट", "ही", "कोड"]
    score = error_counts("curly hair", "கர்லி ஹேர்")
    assert score["hypothesis_words"] == 2
    assert score["substitutions"] == 2
    assert score["insertions"] == 0


def test_empty_recognition_is_all_deleted_speech():
    score = error_counts("keep the announcement", "")
    assert score["deletions"] == 3
    assert score["wer"] == 1


def test_unknown_reference_spans_are_not_treated_as_spoken_words():
    for reference in ("<UNKNOWN/> turn left", "a <UNKOWN/> noise"):
        with pytest.raises(ValueError, match="untranscribed/unknown"):
            error_counts(reference, "turn left")
