"""The language guard in core/asr.py.

Offline: nothing here touches the network. _looks_english is a pure function
and the transcribe path is exercised with the HTTP call monkeypatched out.

WHY THIS IS TESTED AT ALL. The guard exists because the Inference Providers
router gives no way to pin Whisper to English, so auto-detection can return
another script on a badly mispronounced word. That failure is invisible in
code review and only shows up live, on the exact input this app is built to
send. A test is cheaper than finding out during judging.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import asr  # noqa: E402


def test_english_transcripts_pass():
    for text in ["agricultural", "ornithological", "a", "OK.", "Volcanologist!"]:
        assert asr._looks_english(text), text


def test_non_latin_transcripts_rejected():
    # Real detection failures: Whisper guessing the wrong source language and
    # returning that language's script instead of the English word said.
    for text in ["Привет как дела", "这是一个测试", "こんにちは", "مرحبا", "안녕하세요"]:
        assert not asr._looks_english(text), text


def test_digits_only_rejected():
    # "3 2 1" carries no phones to score against a word reference. Sending it
    # through espeak would invent some.
    assert not asr._looks_english("3 2 1")


def test_non_english_transcript_becomes_no_speech(monkeypatch):
    """The whole point: a bad detection must not reach the scorer.

    [] is what the no_speech branch in core/session.py keys on, and that
    branch does not consume a retry. A language-detection miss is our failure,
    not the learner's, so it must not cost them an attempt.
    """
    monkeypatch.setattr(asr, "_whisper_transcribe", lambda _: "Привет как дела")
    assert asr.transcribe_bytes(b"fake") == []


def test_english_transcript_still_phonemized(monkeypatch):
    """The guard must not swallow the normal path.

    _words_to_phones is stubbed rather than called for real: it shells out to
    espeak-ng, which is a system package, and the rest of this suite runs with
    no external dependencies. What is under test is the routing, not espeak.
    """
    seen = []
    monkeypatch.setattr(asr, "_whisper_transcribe", lambda _: "thinking")
    monkeypatch.setattr(asr, "_words_to_phones", lambda t: seen.append(t) or ["θ"])
    assert asr.transcribe_bytes(b"fake") == ["θ"]
    assert seen == ["thinking"], "the transcript must reach the phonemizer intact"


def test_empty_transcript_is_not_the_guards_business(monkeypatch):
    """Silence already returns [] upstream. The guard must not change that
    into something else, or double-log it as a language failure."""
    monkeypatch.setattr(asr, "_whisper_transcribe", lambda _: "")
    assert asr.transcribe_bytes(b"fake") == []
