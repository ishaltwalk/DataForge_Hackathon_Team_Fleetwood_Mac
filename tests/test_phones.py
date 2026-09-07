import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.phones import flatten, normalize, segment  # noqa: E402


def test_stress_marks_are_stripped():
    assert normalize("\u02c8\u03b8\u028c\u0279") == normalize("\u03b8\u028c\u0279")


def test_spaces_are_stripped():
    # The ASR decoder returns space-separated phones; espeak does not.
    assert normalize("\u03b8 \u028c \u0279") == ["\u03b8", "\u028c", "\u0279"]


def test_language_switch_markers_removed():
    assert normalize("(en)\u03b8\u028c") == ["\u03b8", "\u028c"]


def test_diphthong_splits_into_two_segments():
    """Recorded, not asserted as a preference.

    panphon's ipa_segs treats "ou028a" as two segments. That is fine because
    both the reference and the ASR go through this same function, but it means
    a syllable "rou028a" has length 2, which syllable_spans depends on.
    """
    assert segment("o\u028a") == ["o", "\u028a"]


def test_length_mark_stays_attached_to_its_vowel():
    # Dropping it would make short-vs-long vowel errors invisible to scoring.
    assert segment("\u0254\u02d0\u0279") == ["\u0254\u02d0", "\u0279"]


def test_ascii_r_folds_onto_the_ipa_rhotic():
    assert normalize("r") == ["\u0279"]


def test_flatten():
    assert flatten([["\u03b8", "\u028c"], ["l", "i"]]) == ["\u03b8", "\u028c", "l", "i"]


def test_empty_input():
    assert normalize("") == []
    assert normalize("   ") == []
