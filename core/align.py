"""Phoneme alignment with articulatory substitution cost.

Weighted Levenshtein where substituting one phone for another costs the
articulatory feature distance between them, not a flat 1.0. So saying "s"
where "u03B8" was expected costs less than saying "k", because s and u03B8 differ
in fewer features. That is the whole reason this is a pronunciation coach
rather than a spell checker: it can rank how wrong an attempt was, and a
near-miss deserves different feedback from a completely different sound.

The backtrace matters as much as the number. A total distance tells the user
they were wrong; the operation list tells them which phone was wrong, which is
what drives the syllable-level correction downstream.


WHY THE NORMALIZATION EXISTS (do not remove it)
-----------------------------------------------
panphon's weighted_feature_edit_distance is NOT bounded to 0..1. Measured over
a 41-phone English inventory (820 pairs): median 6.4, max 16.75. Left raw
against an insertion/deletion cost of 1.0, deleting a phone and inserting
another (total 2.0) is cheaper than almost every substitution, so the aligner
stops aligning mismatched phones altogether and emits del+ins pairs instead.
Every op then carries ref_index None or a flat cost, syllable blame collapses,
and the scores still look plausible while meaning nothing.

So substitution cost is divided by MAX_WEIGHTED_DISTANCE, putting it on 0..1
where 1.0 is "as different as two English phones get". INS_COST and DEL_COST
sit at that same ceiling, which reads as: dropping a sound is as bad as
replacing it with the most unrelated sound available.

The unweighted feature_edit_distance is already normalized and would avoid
this, but it compresses the useful range (max 0.44 over the same inventory)
and weakens exactly the discrimination this app rests on: weighted gives
th/s vs th/k a 6.3x ratio, unweighted only 2.8x.
"""

from functools import lru_cache

import panphon.distance

_dst = panphon.distance.Distance()

# Measured over all 820 pairs in a 41-phone English inventory: median 6.4,
# max 16.75. The divisor is the MEDIAN, not the max, and that choice matters.
# The max is set by pairs no learner ever confuses (a stop against a rhotic
# vowel), so dividing by it crushes every realistic error into noise: th->s
# would cost 0.03 and a whole word would still score 0.996 after being said
# wrong. Dividing by the median puts 1.0 at "as different as two arbitrary
# English phones" and gives real confusions the usable part of the range:
# th/s 0.07, th/k 0.45, r/l 0.50, v/w 0.89. Costs above the median clip to 1.0.
MAX_WEIGHTED_DISTANCE = 7.0

# A substitution costs at most 1.0 after normalization, so insertion and
# deletion at 1.0 mean "as bad as the worst possible substitution". This keeps
# the aligner preferring a substitution whenever the phones are related at all,
# which is what produces usable per-syllable blame.
INS_COST = 1.0
DEL_COST = 1.0

# Phones panphon has no feature vector for. Logged rather than swallowed: if
# one of these recurs, it belongs in core.phones._ALIAS instead.
UNKNOWN_PHONES: set[str] = set()


@lru_cache(maxsize=100_000)
def sub_cost(a: str, b: str) -> float:
    """Normalized articulatory distance between two phones, 0.0 if identical.

    Cached because the DP asks for the same pairs thousands of times per
    utterance and panphon's lookup is not cheap.
    """
    if a == b:
        return 0.0
    try:
        d = _dst.weighted_feature_edit_distance(a, b)
    except Exception:
        UNKNOWN_PHONES.update([a, b])
        return 1.0
    if d is None:
        UNKNOWN_PHONES.update([a, b])
        return 1.0
    return min(float(d) / MAX_WEIGHTED_DISTANCE, 1.0)


def align(ref: list[str], hyp: list[str]) -> tuple[float, list[tuple]]:
    """Align a reference phone sequence against a heard one.

    Returns (total_cost, ops) where each op is
        (kind, ref_index, ref_phone, hyp_phone, cost)
    and kind is one of "ok", "sub", "del", "ins".

    ref_index is the position in ref that the op refers to, or None for an
    insertion (the user said a sound that has no counterpart in the reference,
    so there is nothing to attribute it to).
    """
    n, m = len(ref), len(hyp)

    dist = [[0.0] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple | None]] = [[None] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dist[i][0] = dist[i - 1][0] + DEL_COST
        back[i][0] = ("del", i - 1)
    for j in range(1, m + 1):
        dist[0][j] = dist[0][j - 1] + INS_COST
        back[0][j] = ("ins", None)

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            c = sub_cost(ref[i - 1], hyp[j - 1])
            candidates = [
                (dist[i - 1][j - 1] + c, ("sub", i - 1)),
                (dist[i - 1][j] + DEL_COST, ("del", i - 1)),
                (dist[i][j - 1] + INS_COST, ("ins", None)),
            ]
            dist[i][j], back[i][j] = min(candidates, key=lambda x: x[0])

    ops: list[tuple] = []
    i, j = n, m
    while i > 0 or j > 0:
        kind, ri = back[i][j]
        if kind == "sub":
            c = sub_cost(ref[i - 1], hyp[j - 1])
            label = "ok" if c == 0.0 else "sub"
            ops.append((label, ri, ref[i - 1], hyp[j - 1], c))
            i, j = i - 1, j - 1
        elif kind == "del":
            ops.append(("del", ri, ref[i - 1], None, DEL_COST))
            i -= 1
        else:
            ops.append(("ins", None, None, hyp[j - 1], INS_COST))
            j -= 1

    ops.reverse()
    return dist[n][m], ops


def describe(ops: list[tuple]) -> str:
    """Human-readable diff, for the UI and for debugging."""
    parts = []
    for kind, _ri, rp, hp, _c in ops:
        if kind == "ok":
            parts.append(rp)
        elif kind == "sub":
            parts.append(f"[{rp}->{hp}]")
        elif kind == "del":
            parts.append(f"[{rp}->_]")
        else:
            parts.append(f"[_->{hp}]")
    return " ".join(parts)
