"""Rime payload construction, offline.

These are the two mistakes that produce audio which sounds fine on a good clip
and is wrong on the clip that matters, so neither is catchable by ear during a
demo. Both were live bugs before the merge.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.correct import INLINE_SPEED, build_correction, build_prompt  # noqa: E402
from rime_tts.synthesize import build_payload  # noqa: E402

ENTRY = {
    "id": "culture",
    "display": "culture",
    "ipa_syllables": [["k", "ʌ", "l", "t"], ["ʃ", "ə", "ɹ"]],
    "rpa_syllables": ["k1AlC", "0xr"],
}


def test_brackets_force_phonemization_even_if_caller_forgets():
    p = build_payload("{k1AlC}-{0xr}")
    assert p["phonemizeBetweenBrackets"] is True


def test_plain_text_does_not_set_phonemize():
    p = build_payload("Hello there.")
    assert "phonemizeBetweenBrackets" not in p


def test_one_speed_value_per_bracketed_span():
    # Two wrong syllables means two bracketed spans. A single value leaves the
    # second span at full speed, so the correction silently stops correcting
    # exactly when the attempt was worst.
    payload = build_correction(ENTRY, {0, 1})
    assert payload["inline_speed"] == f"{INLINE_SPEED},{INLINE_SPEED}"
    assert payload["text"] == "[{k1AlC}]-[{0xr}]"


def test_one_wrong_syllable_brackets_only_that_one():
    payload = build_correction(ENTRY, {1})
    assert payload["text"] == "{k1AlC}-[{0xr}]"
    assert payload["inline_speed"] == INLINE_SPEED


def test_no_wrong_syllables_sends_no_speed_override():
    payload = build_correction(ENTRY, set())
    assert payload["inline_speed"] is None


def test_prompt_is_one_unbracketed_chunk():
    payload = build_prompt(ENTRY)
    assert payload["text"] == "{k1AlC0xr}"
    assert "[" not in payload["text"]


def test_speed_is_sent_through_to_the_request_body():
    payload = build_correction(ENTRY, {1})
    body = build_payload(
        payload["text"],
        phonemize_brackets=payload["phonemize_brackets"],
        inline_speed=payload["inline_speed"],
    )
    assert body["inlineSpeedAlpha"] == INLINE_SPEED
    assert body["modelId"] == "mistv3"
