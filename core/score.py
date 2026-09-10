from core.align import align
from core.phones import flatten

PASS_THRESHOLD = 0.90
SYL_THRESHOLD = 0.05
MIN_PHONES = 2


def syllable_spans(ipa_syllables: list[list[str]]) -> list[tuple[int, int]]:
    spans, k = [], 0
    for syl in ipa_syllables:
        assert isinstance(syl, list), "syllables must be lists of segments"
        spans.append((k, k + len(syl)))
        k += len(syl)
    return spans


def score(entry: dict, hyp_phones: list[str]) -> dict:
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
            continue
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
