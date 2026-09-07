"""Syllable-level scoring.

Turns a phone-level alignment into the one thing the rest of the app needs:
which syllable was wrong. The correction step indexes rpa_syllables by that
number, so the syllable arrays in data/words.json must have equal length on
both the IPA and RPA sides. validate_bank() enforces it.

Two thresholds, not one. A word can average acceptably while one syllable is
badly wrong, and that is exactly the case this product exists to catch, so a
word passes only if the overall score is high AND no single syllable is bad.

Both thresholds are set empirically in scripts/calibrate.py, not guessed.
"""

from core.align import align
from core.phones import flatten

# Informed starting points, NOT final. Replace both from evidence/calibration.md
# once real clips have been measured. Do not tune these by feel.
#
# WHICH ONE ACTUALLY DETECTS ERRORS
# ---------------------------------
# The syllable gate does the work; the overall score is mostly for display.
# Measured on simulated single-phone errors against the committed word bank:
#
#   error                overall score   worst syllable cost
#   th -> s              0.990           0.071
#   th -> k              0.936           0.446
#   r  -> l              0.929           0.500
#   v  -> w              0.901           0.893
#   whole syllable lost  0.700           3.000
#
# One wrong phone in a seven-phone word moves the average by about 1%, because
# that is arithmetically what one phone out of seven is worth. So a pass gate
# built on the overall score alone would wave through every single-phone error,
# which is every error this app exists to catch. The syllable cost separates
# them cleanly, which is why SYL_THRESHOLD is small and does the real work.
PASS_THRESHOLD = 0.90
SYL_THRESHOLD = 0.05

# Fewer phones than this means silence, a clipped recording, or a mic failure.
# Scoring it would tell a confused user their pronunciation was terrible.
MIN_PHONES = 2


def syllable_spans(ipa_syllables: list[list[str]]) -> list[tuple[int, int]]:
    """[['u03b8','u028c'], ['l','i']] -> [(0,2), (2,4)]

    Index ranges into the flattened reference. Note len() here is a segment
    count because core.phones.segment() produced these lists; if a syllable is
    ever stored as a plain string, every span silently shifts.
    """
    spans, k = [], 0
    for syl in ipa_syllables:
        assert isinstance(syl, list), "syllables must be lists of segments"
        spans.append((k, k + len(syl)))
        k += len(syl)
    return spans


def score(entry: dict, hyp_phones: list[str]) -> dict:
    """Score one attempt against one word bank entry."""
    n_syl = len(entry["ipa_syllables"])

    if len(hyp_phones) < MIN_PHONES:
        return {
            "status": "no_speech",
            "score": 0.0,
            "passed": False,
            "syllable_costs": [0.0] * n_syl,
            "worst_syllable": None,
            "ops": [],
            "heard": hyp_phones,
        }

    ref = flatten(entry["ipa_syllables"])
    total, ops = align(ref, hyp_phones)
    spans = syllable_spans(entry["ipa_syllables"])

    syl_cost = [0.0] * n_syl
    for _kind, ri, _rp, _hp, cost in ops:
        if ri is None:
            continue  # insertion, no reference position to blame
        for s, (lo, hi) in enumerate(spans):
            if lo <= ri < hi:
                syl_cost[s] += cost
                break

    normalized = max(1.0 - total / max(len(ref), 1), 0.0)
    worst = max(range(n_syl), key=lambda s: syl_cost[s])

    return {
        "status": "ok",
        "score": round(normalized, 3),
        "passed": normalized >= PASS_THRESHOLD and syl_cost[worst] <= SYL_THRESHOLD,
        "syllable_costs": [round(c, 3) for c in syl_cost],
        "worst_syllable": worst,
        "worst_cost": round(syl_cost[worst], 3),
        "total_cost": round(total, 3),
        "ops": ops,
        "heard": hyp_phones,
    }


def validate_bank(bank: list[dict]) -> None:
    """Fail loudly if the IPA and RPA syllable arrays ever disagree.

    This is the bug that passes every unit test and breaks the live demo: if
    the two arrays have different lengths or different split points,
    worst_syllable points at a different sound on each side and the app
    confidently corrects the wrong syllable.
    """
    seen = set()
    for e in bank:
        wid = e["id"]
        assert wid not in seen, f"duplicate word id: {wid}"
        seen.add(wid)
        n_ipa = len(e["ipa_syllables"])
        n_rpa = len(e["rpa_syllables"])
        assert n_ipa == n_rpa, (
            f"{wid}: {n_ipa} IPA syllables but {n_rpa} RPA syllables. "
            "Both columns must split the word at the same points."
        )
        assert n_ipa > 0, f"{wid}: empty syllable list"
        for syl in e["ipa_syllables"]:
            assert isinstance(syl, list) and syl, f"{wid}: bad IPA syllable {syl!r}"
