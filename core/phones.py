"""Shared phone normalization.

Both sides of the comparison go through normalize():
  * the espeak-ng reference (core.g2p)
  * the wav2vec2 ASR output (core.asr)

If these ever diverge, every distance in the system becomes meaningless while
still looking like plausible numbers, so there is exactly one function here and
both callers use it. Do not write a second one.

Two decisions recorded here because they are judgment calls, not facts:

LENGTH MARKS (u02D0) are KEPT and attached to the preceding vowel. Dropping
them makes short-vs-long vowel errors invisible to the scorer, which matters
because some trap words are chosen precisely for that contrast.

DIPHTHONGS are split into two segments. panphon's ipa_segs() treats "ou028A"
as ['o', 'u028A'] rather than one unit. That is fine and self-consistent as
long as both sides use this function, but it means a syllable like "rou028A"
has length 2 in ipa_syllables, not 1. Verified empirically, see
tests/test_phones.py::test_diphthong_splits_into_two.
"""

import re

import panphon

_ft = panphon.FeatureTable()

# Stress digits and marks, tie bars, linking marks, whitespace.
_STRESS = "\u02c8\u02cc'"          # primary stress, secondary stress, apostrophe
_TIES = "\u0361\u035c\u203f"       # combining ties, undertie
_DROP = _STRESS + _TIES + " \t\n"

# espeak emits language-switch markers like "(en)" inside its output.
_LANG_SWITCH = re.compile(r"\(.*?\)")

# ASR sometimes emits symbols panphon has no features for. Fold the known ones
# onto their nearest featural equivalent instead of losing them to the
# unknown-symbol path in core.align.
_ALIAS = {
    "r": "\u0279",   # alveolar trill -> alveolar approximant (English rhotic)
    "g": "\u0261",   # ASCII g -> IPA script g
    ":": "\u02d0",   # ASCII colon used as a length mark
}

LENGTH_MARK = "\u02d0"


def segment(s: str) -> list[str]:
    """Split an IPA string into phone segments, keeping length marks attached."""
    segs = _ft.ipa_segs(s)
    if not segs:
        return []

    merged: list[str] = []
    for seg in segs:
        if seg == LENGTH_MARK and merged:
            merged[-1] = merged[-1] + LENGTH_MARK
        else:
            merged.append(seg)
    return merged


def normalize(raw: str) -> list[str]:
    """espeak string or ASR string -> list of bare phone segments."""
    s = _LANG_SWITCH.sub("", raw.strip())
    for ch in _DROP:
        s = s.replace(ch, "")
    s = "".join(_ALIAS.get(ch, ch) for ch in s)
    return segment(s)


def flatten(syllables: list[list[str]]) -> list[str]:
    """[['u03b8','u028C'], ['l','i']] -> ['u03b8','u028C','l','i']"""
    return [p for syl in syllables for p in syl]
