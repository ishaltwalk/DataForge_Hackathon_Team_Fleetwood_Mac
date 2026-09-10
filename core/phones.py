import re

import panphon

_ft = panphon.FeatureTable()

_STRESS = "\u02c8\u02cc'"
_TIES = "\u0361\u035c\u203f"
_DROP = _STRESS + _TIES + " \t\n"

_LANG_SWITCH = re.compile(r"\(.*?\)")

_ALIAS = {
    "r": "\u0279",
    "g": "\u0261",
    ":": "\u02d0",
}

_DECOMPOSE = {
    "\u025a": "\u0259\u0279",
    "\u1d7b": "\u026a",
    "\u02b2": "j",
}

_INTENTIONAL = "\u0303\u0329"

LOST_SYMBOLS: set[str] = set()
LENGTH_MARK = "\u02d0"


def segment(s: str) -> list[str]:
    for bad, good in _DECOMPOSE.items():
        s = s.replace(bad, good)
    for ch in _INTENTIONAL:
        s = s.replace(ch, "")
    while "\u0279\u0279" in s:
        s = s.replace("\u0279\u0279", "\u0279")

    segs = _ft.ipa_segs(s)

    if "".join(segs) != s:
        kept = "".join(segs)
        for ch in s:
            if ch not in kept:
                LOST_SYMBOLS.add(ch)
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
    s = _LANG_SWITCH.sub("", raw.strip())
    for ch in _DROP:
        s = s.replace(ch, "")
    s = "".join(_ALIAS.get(ch, ch) for ch in s)
    return segment(s)


def flatten(syllables: list[list[str]]) -> list[str]:
    return [p for syl in syllables for p in syl]
