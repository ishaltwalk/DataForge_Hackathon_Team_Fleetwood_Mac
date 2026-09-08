"""The coaching turn, with Rime stubbed out.

THE ASSERTION THAT MATTERS is test_highlighted_syllables_are_the_spoken_ones.
Both front ends draw `turn.wrong` and both play `turn.spoken`. If those two
are ever computed from different inputs, the app highlights one syllable and
enunciates another, and nothing in the code looks wrong. This test pulls the
bracketed indices back out of the text that was actually sent to Rime and
compares them to the set the UI was told to highlight.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from core import coach, speech  # noqa: E402
from core.phones import flatten  # noqa: E402
from core.session import Session  # noqa: E402

ENTRY = {
    "id": "culture",
    "display": "culture",
    "trap": "ch",
    "ipa_syllables": [["k", "ʌ", "l", "t"], ["ʃ", "ə", "ɹ"]],
    "rpa_syllables": ["k1AlC", "0xr"],
}

CORRECT = flatten(ENTRY["ipa_syllables"])


@pytest.fixture(autouse=True)
def stub_rime(monkeypatch):
    """No network in unit tests. Record what would have been sent."""
    sent = []

    def fake_speak(**payload):
        sent.append(payload)
        return speech.Spoken(audio=b"RIFFfake", provider="rime")

    monkeypatch.setattr(coach, "speak", fake_speak)
    return sent


def bracketed_indices(text: str) -> set[int]:
    """'{k1AlC}-[{0xr}]' -> {1}"""
    return {i for i, chunk in enumerate(text.split("-")) if chunk.startswith("[")}


def test_perfect_attempt_passes_and_says_nothing():
    turn = coach.take_turn(ENTRY, CORRECT, Session(ENTRY))
    assert turn.state == "pass"
    assert turn.wrong == set()
    assert turn.spoken is None


def test_silence_is_not_an_attempt():
    turn = coach.take_turn(ENTRY, ["k"], Session(ENTRY))
    assert turn.state == "no_speech"
    assert turn.attempts == 0
    assert turn.spoken is None


def test_highlighted_syllables_are_the_spoken_ones(stub_rime):
    # Break the second syllable: ʃ -> s, the classic "cul-ture" -> "cul-ser".
    heard = ["k", "ʌ", "l", "t", "s", "ə", "ɹ"]
    turn = coach.take_turn(ENTRY, heard, Session(ENTRY))

    assert turn.state == "retry"
    assert turn.wrong, "a failed attempt must blame at least one syllable"
    assert bracketed_indices(stub_rime[-1]["text"]) == turn.wrong


def test_blames_the_syllable_that_was_actually_broken():
    heard = ["k", "ʌ", "l", "t", "s", "ə", "ɹ"]
    turn = coach.take_turn(ENTRY, heard, Session(ENTRY))
    assert turn.wrong == {1}


def test_correction_is_never_readable_text(stub_rime):
    heard = ["k", "ʌ", "l", "t", "s", "ə", "ɹ"]
    turn = coach.take_turn(ENTRY, heard, Session(ENTRY))
    # The coaching line names a position, never the sound to make. If it ever
    # spells the phoneme out, the voice has stopped being necessary.
    assert turn.coaching == "The second syllable is the one to fix."
    for symbol in ("ʃ", "C", "{", "["):
        assert symbol not in turn.coaching


def test_gives_up_after_max_attempts_and_replays_the_whole_word(stub_rime):
    sess = Session(ENTRY, max_attempts=2)
    heard = ["k", "ʌ", "l", "t", "s", "ə", "ɹ"]
    assert coach.take_turn(ENTRY, heard, sess).state == "retry"
    turn = coach.take_turn(ENTRY, heard, sess)
    assert turn.state == "give_up"
    assert "[" not in stub_rime[-1]["text"], "the give-up replay is not slowed"


def test_provider_failure_is_reported_not_swallowed(monkeypatch):
    monkeypatch.setattr(
        coach,
        "speak",
        lambda **_: speech.Spoken(audio=None, provider="unavailable", reason="429"),
    )
    heard = ["k", "ʌ", "l", "t", "s", "ə", "ɹ"]
    turn = coach.take_turn(ENTRY, heard, Session(ENTRY))
    assert turn.spoken.provider == "unavailable"
    assert turn.spoken.ok is False
