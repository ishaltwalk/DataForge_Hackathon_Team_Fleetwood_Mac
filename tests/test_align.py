import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.align import DEL_COST, align, sub_cost  # noqa: E402
from core.score import score, syllable_spans, validate_bank  # noqa: E402

TH, S, K, A, L, I, R, OW = "\u03b8", "s", "k", "\u028c", "l", "i", "\u0279", "o\u028a"


def entry(syllables, rpa=None):
    return {
        "id": "test",
        "display": "test",
        "ipa_syllables": syllables,
        "rpa_syllables": rpa if rpa is not None else ["x"] * len(syllables),
    }


# --- alignment ---------------------------------------------------------


def test_identical_sequences_cost_nothing():
    total, ops = align([TH, A, L], [TH, A, L])
    assert total == 0.0
    assert all(op[0] == "ok" for op in ops)


def test_near_miss_costs_less_than_a_far_miss():
    """The entire justification for using articulatory distance.

    Saying "s" for "th" is one or two features off. Saying "k" for "th" is a
    different place and manner. A flat edit distance would score both as 1.0
    and the coach could not tell a close attempt from a hopeless one.
    """
    assert sub_cost(TH, S) < sub_cost(TH, K)


def test_substitution_is_cheaper_than_deletion_for_a_near_miss():
    near, _ = align([TH, A], [S, A])
    dropped, _ = align([TH, A], [A])
    assert near < dropped


def test_deletion_costs_one():
    total, ops = align([TH, A, L], [TH, A])
    assert total == DEL_COST
    assert [op[0] for op in ops].count("del") == 1


def test_insertion_has_no_reference_index():
    _total, ops = align([TH, A], [TH, A, L])
    inserts = [op for op in ops if op[0] == "ins"]
    assert len(inserts) == 1
    assert inserts[0][1] is None


def test_ops_carry_the_reference_position():
    _total, ops = align([TH, A, L], [S, A, L])
    subs = [op for op in ops if op[0] == "sub"]
    assert len(subs) == 1
    assert subs[0][1] == 0          # the first phone was the wrong one
    assert subs[0][2] == TH
    assert subs[0][3] == S


# --- syllable spans ----------------------------------------------------


def test_spans_are_segment_counts_not_string_lengths():
    # "rou028a" is two segments, so the second span must be width 2.
    spans = syllable_spans([[TH, A], [R, "o"], [L, I]])
    assert spans == [(0, 2), (2, 4), (4, 6)]


# --- scoring -----------------------------------------------------------


def test_perfect_attempt_passes():
    e = entry([[TH, A], [L, I]])
    r = score(e, [TH, A, L, I])
    assert r["status"] == "ok"
    assert r["score"] == 1.0
    assert r["passed"] is True
    assert r["syllable_costs"] == [0.0, 0.0]


def test_blame_lands_on_the_syllable_that_was_wrong():
    """The assertion the whole product rests on.

    Failing is not enough. The correction step indexes rpa_syllables by
    worst_syllable, so if this points at the wrong syllable the app confidently
    enunciates the wrong sound.
    """
    e = entry([[TH, A], [L, I]])
    r = score(e, [TH, A, K, I])          # second syllable broken
    assert r["worst_syllable"] == 1
    assert r["syllable_costs"][1] > r["syllable_costs"][0]


def test_blame_lands_on_the_first_syllable_too():
    e = entry([[TH, A], [L, I]])
    r = score(e, [S, A, L, I])           # first syllable broken
    assert r["worst_syllable"] == 0
    assert r["passed"] is False or r["syllable_costs"][0] > 0


def test_one_bad_syllable_fails_even_when_the_average_is_fine():
    """Why there are two thresholds instead of one.

    A long word with a single badly wrong syllable can still average above the
    overall pass line. That is exactly the case this app exists to catch.
    """
    e = entry([[TH, A], [L, I], [L, I], [L, I]])
    r = score(e, [K, A, L, I, L, I, L, I])
    assert r["score"] > 0.8              # average looks acceptable
    assert r["worst_syllable"] == 0


def test_silence_is_reported_not_scored():
    e = entry([[TH, A], [L, I]])
    r = score(e, [])
    assert r["status"] == "no_speech"
    assert r["passed"] is False
    assert r["worst_syllable"] is None


def test_syllable_cost_list_always_matches_the_syllable_count():
    e = entry([[TH, A], [L, I], [R, "o"]])
    for heard in ([], [TH], [TH, A, L, I, R, "o"], [K, K, K]):
        r = score(e, heard)
        assert len(r["syllable_costs"]) == 3


# --- word bank validation ---------------------------------------------


def test_validator_catches_mismatched_syllable_counts():
    bad = [{"id": "w", "ipa_syllables": [[TH], [A]], "rpa_syllables": ["x"]}]
    try:
        validate_bank(bad)
    except AssertionError as exc:
        assert "split the word at the same points" in str(exc)
    else:
        raise AssertionError("validator should have rejected the mismatch")


def test_validator_accepts_a_good_entry():
    validate_bank([{"id": "w", "ipa_syllables": [[TH], [A]], "rpa_syllables": ["a", "b"]}])


# --- regression: cost scale --------------------------------------------


def test_substitution_costs_are_normalized():
    """Guards the bug that silently breaks everything downstream.

    panphon's raw weighted distance goes up to ~16.75. If sub_cost ever
    returns raw values again, del+ins (2.0) becomes cheaper than most
    substitutions, the aligner stops aligning mismatched phones, and syllable
    blame collapses while the scores still look plausible.
    """
    for a, b in [(TH, S), (TH, K), (R, L), ("v", "w"), (I, "\u026a")]:
        assert 0.0 <= sub_cost(a, b) <= 1.0, (a, b, sub_cost(a, b))


def test_related_phones_prefer_substitution_over_delete_plus_insert():
    _total, ops = align([TH, A, L], [S, A, L])
    kinds = [op[0] for op in ops]
    assert "sub" in kinds
    assert "del" not in kinds and "ins" not in kinds
