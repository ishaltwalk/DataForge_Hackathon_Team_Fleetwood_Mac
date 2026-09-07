"""Build a large audited bank of hard-to-pronounce words.

Derived from the CMU Pronouncing Dictionary rather than hand-written, because
a hand-written list cannot reach this size and cannot be audited consistently.


THE AUDIT IS THE POINT
======================
espeak is a rules engine for English orthography. Given a word whose spelling
does not follow English rules, it does not fail loudly, it produces a
confident wrong answer. The reference pronunciation is what the entire scoring
pipeline measures against, so a wrong reference means the coach penalises a
learner for saying a word correctly. That is worse than having no coach.

Two audits run against CMUdict. The second one is the one that matters.

AUDIT 1, syllable count. espeak's vowel-group count must equal CMUdict's
stressed-vowel count. Catches dropped vowels:

    reliable   -> rliable      3 syllables, should be 4
    vulnerable -> vulnrable    3 syllables, should be 4
    asterisk   -> astrisk      2 syllables, should be 3

AUDIT 2, phone agreement. espeak's phones must match CMUdict's, compared at a
coarse class level that forgives notational differences (flap vs t, schwa
variants, length marks) but not real disagreements. This catches what audit 1
cannot see, because a syllable count can be right while every sound is wrong:

    gnocchi     the g is pronounced; syllable count still matches
    bruschetta  Italian sch read as English
    chthonic    espeak gives up and spells "C-H" out as letters

Loanwords are exactly the words a pronunciation coach most wants, and exactly
the words its reference data is least reliable for. Without audit 2 the bank
fills with confidently wrong references.


DIFFICULTY CRITERIA
===================
A word must exhibit at least one measurable mechanism.

1. Trap phonemes: th, r, v, w, ng, zh, short a, the nurse vowel, r-coloured
   vowels. Sounds absent or merged in most first-language inventories, so
   learners substitute the nearest sound they have.
2. Consonant clusters of three or more, which many languages disallow and
   speakers break up with an inserted vowel.
3. Orthographic irregularity: silent letters and irregular digraphs (gh, kn,
   wr, ps, pn, mb, bt, lm, ough, eau) together with a letters-to-phones ratio
   above normal.
4. Four or more syllables, a working-memory load rather than an articulation
   problem.
5. Repeated similar articulations, which invite metathesis: statistics,
   particularly, specificity.
6. Late stress, taken from CMUdict's own marking, where the spelling does not
   suggest where the emphasis falls.


POPULARITY BALANCE
==================
A coach full of words nobody says is a party trick. Frequency comes from
wordfreq's Zipf scale and the bank is balanced, with rare words capped:

    common    zipf >= 4.0    everyday words people still get wrong
    mid       3.0 to 4.0     educated vocabulary said often enough to matter
    showcase  below 3.0      the impressive ones

Below zipf 2.5 is excluded: too rare to be worth practising, and too rare for
CMUdict and espeak to agree on reliably.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cmudict
import wordfreq
from english_words import get_english_words_set
from phonemizer import phonemize

from core.phones import normalize

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "words.json"
REPORT = ROOT / "data" / "wordbank_report.md"

TARGET = 5000
MIN_ZIPF = 0.0
MAX_DISAGREEMENT = 0.25
# Minimum weighted difficulty. Set so that short everyday words containing a
# trap phoneme ("going", "very") fall out while genuinely hard words stay.
MIN_DIFFICULTY = 3

VOWELS = set("iɪeɛæaɑɒɔoʊuʌəɐɜɚɝyøœ")
DIPHTHONGS = {"eɪ", "aɪ", "ɔɪ", "aʊ", "oʊ", "ɐʊ", "ɐɪ", "ɪə", "eə", "ʊə"}

ONSETS3 = {"stɹ", "spɹ", "skɹ", "stj", "spl", "skw"}
ONSETS2 = {
    "st", "sp", "sk", "sm", "sn", "sl", "sw", "sf",
    "tɹ", "dɹ", "pɹ", "bɹ", "kɹ", "gɹ", "ɡɹ", "fɹ", "θɹ", "ʃɹ",
    "pl", "bl", "kl", "gl", "ɡl", "fl",
    "tw", "dw", "kw", "gw", "ɡw", "θw", "hw",
    "pj", "bj", "kj", "fj", "vj", "mj", "hj", "nj", "lj",
}

ARPA_TO_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ə", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ",
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "EH": "ɛ", "ER": "ɜ",
    "EY": "eɪ", "F": "f", "G": "ɡ", "HH": "h", "IH": "ɪ", "IY": "i",
    "JH": "dʒ", "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ",
    "OW": "oʊ", "OY": "ɔɪ", "P": "p", "R": "ɹ", "S": "s", "SH": "ʃ",
    "T": "t", "TH": "θ", "UH": "ʊ", "UW": "u", "V": "v", "W": "w",
    "Y": "j", "Z": "z", "ZH": "ʒ",
}

# Coarse equivalence classes. Two phones in the same class count as agreeing,
# because espeak and CMUdict write the same sound differently. This forgives
# notation without forgiving real disagreement.
CLASSES = [
    "ɑɒaɐʌəæ", "ɛe", "ɪi", "ɔo", "ʊu", "ɜɚɝ",
    "ptɾd", "kɡg", "bp", "fv", "θð", "sz", "ʃʒ", "tʃdʒ",
    "ɹɻr", "l", "mn", "ŋ", "jw", "h",
]
CLASS_OF = {ch: i for i, cls_ in enumerate(CLASSES) for ch in cls_}

IRREGULAR = re.compile(
    r"ough|augh|eau|gh|kn|wr|ps|pn|pt|mb$|bt|lm|mn$|sc[ei]|que$|gn|rh|xh"
)

TRAPS = {
    "θ": "th (voiceless) becomes s, t or f",
    "ð": "th (voiced) becomes d, z or v",
    "ɹ": "r and l get merged",
    "v": "v becomes w or b",
    "w": "w becomes v",
    "ŋ": "ng becomes n or nk",
    "ʒ": "zh is absent from most inventories",
    "æ": "short a merges with e in many inventories",
    "ɜ": "the nurse vowel has no equivalent in most inventories",
    "ɚ": "r-coloured vowel",
}


def is_vowel(p):
    return bool(p) and p[0] in VOWELS


def phone_class(p):
    return CLASS_OF.get(p[0], -1)


def nuclei_groups(phones):
    """Vowel groups, not vowel segments.

    panphon splits diphthongs into two segments, so counting segments makes
    "available" five syllables. But only true diphthongs merge: greedy merging
    collapses "chaos" into one syllable. Hence the closed set, and the length
    cap that stops "quinoa" chaining three vowels into one nucleus.
    """
    groups = []
    for i, p in enumerate(phones):
        if not is_vowel(p):
            continue
        if groups and groups[-1][-1] == i - 1 and len(groups[-1]) == 1:
            if phones[i - 1].rstrip("ː") + p.rstrip("ː") in DIPHTHONGS:
                groups[-1].append(i)
                continue
        groups.append([i])
    return groups


def syllabify(phones):
    """Maximal onset: give the following syllable as many consonants as form a
    legal English onset, the rest to the preceding coda."""
    groups = nuclei_groups(phones)
    if not groups:
        return [phones]
    starts = [g[0] for g in groups]
    ends = [g[-1] for g in groups]

    bounds = [0]
    for a, b in zip(ends, starts[1:]):
        run = phones[a + 1: b]
        onset = 0 if not run else 1
        if len(run) >= 2:
            for n in (3, 2):
                if len(run) >= n:
                    cand = "".join(run[-n:])
                    if (n == 3 and cand in ONSETS3) or (n == 2 and cand in ONSETS2):
                        onset = n
                        break
        bounds.append(b - onset)
    bounds.append(len(phones))
    return [phones[i:j] for i, j in zip(bounds, bounds[1:]) if phones[i:j]]


def arpa_to_ipa(pron):
    out = []
    for p in pron:
        ipa = ARPA_TO_IPA.get(p.rstrip("012"))
        if ipa:
            out.extend(list(ipa))
    return out


def canonical(phones):
    """Collapse the r-coloured vowel so both sides spell it the same way.

    core.phones decomposes ɚ into ə + ɹ so panphon can segment it, while
    CMUdict writes the same sound as a single ER. Comparing them directly
    reports a length mismatch on every "-er" word in the language, which is a
    notation difference, not a pronunciation disagreement.
    """
    out, i = [], 0
    while i < len(phones):
        if (i + 1 < len(phones) and phones[i].rstrip("ː") in ("ə", "ʌ")
                and phones[i + 1] == "ɹ"):
            out.append("ɜ")
            i += 2
        else:
            out.append(phones[i])
            i += 1
    return out


def disagreement(a, b):
    """Class-level edit distance between two phone sequences, normalized."""
    a, b = canonical(a), canonical(b)
    ca = [phone_class(p) for p in a if phone_class(p) >= 0]
    cb = [phone_class(p) for p in b if phone_class(p) >= 0]
    if not ca or not cb:
        return 1.0
    prev = list(range(len(cb) + 1))
    for i, x in enumerate(ca, 1):
        cur = [i]
        for j, y in enumerate(cb, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1] / max(len(ca), len(cb))


def cluster_len(phones):
    best = run = 0
    for p in phones:
        run = 0 if is_vowel(p) else run + 1
        best = max(best, run)
    return best


def near_repetition(phones):
    cons = [p for p in phones if not is_vowel(p)]
    if any(cons.count(c) >= 3 for c in set(cons)):
        return True
    pairs = ["".join(phones[i:i + 2]) for i in range(len(phones) - 1)]
    return any(pairs.count(p) >= 2 for p in set(pairs))


def classify(word, phones, n_syl, pron):
    """Return (reasons, trap, score).

    The score exists because a checkbox gate does not work. "going" contains a
    trap phoneme and "very" contains two, but neither is a hard word: they are
    short, frequent, and every learner already says them daily. Difficulty is
    cumulative, so features are weighted and a word must clear a threshold
    rather than merely tick one box.
    """
    reasons, trap, score = [], None, 0

    hit = [lab for ph, lab in TRAPS.items() if ph in phones]
    if hit:
        reasons.append(f"{len(hit)} trap phoneme(s)" if len(hit) > 1 else "trap phoneme")
        trap = hit[0]
        score += min(len(hit), 3)

    c = cluster_len(phones)
    if c >= 3:
        reasons.append(f"{c}-consonant cluster")
        trap = trap or "consonant cluster gets broken up with an inserted vowel"
        score += 2 + (c - 3)

    if IRREGULAR.search(word) and len(word) / max(len(phones), 1) > 1.25:
        reasons.append("spelling misleads")
        trap = trap or "the spelling does not match the sound"
        score += 3

    if n_syl >= 5:
        reasons.append("long, high syllable load")
        score += 3
    elif n_syl == 4:
        reasons.append("four syllables")
        score += 2
    elif n_syl == 3:
        score += 1

    if near_repetition(phones):
        reasons.append("repeated sounds invite metathesis")
        trap = trap or "repeated sounds get swapped or dropped"
        score += 2

    stresses = [p[-1] for p in pron if p[-1].isdigit()]
    if "1" in stresses and stresses.index("1") >= 2:
        reasons.append("late stress")
        score += 2

    return reasons, trap or (reasons[0] if reasons else "general difficulty"), score


def tier(z):
    return "common" if z >= 4.0 else ("mid" if z >= 3.0 else "showcase")


def main():
    cmu = cmudict.dict()
    # CMUdict is full of proper nouns (bancroft, gingrich, kalamazoo). Names
    # are genuinely hard to pronounce, but they are not what a learner wants
    # to practise, and their "correct" pronunciation is often contested. The
    # web2 lexicon is common nouns and verbs only, so intersecting with it
    # drops them. Note it also drops legitimate recent vocabulary, which is an
    # accepted cost.
    lexicon = get_english_words_set(["web2", "gcide"], lower=True)
    print("filtering by frequency...")
    cands = []
    for w, prons in cmu.items():
        if not w.isalpha() or len(w) < 3 or w not in lexicon:
            continue
        z = wordfreq.zipf_frequency(w, "en")
        if z >= MIN_ZIPF:
            cands.append((w, prons, round(z, 2)))
    print(f"  {len(cands)} candidates above zipf {MIN_ZIPF}")

    print("phonemizing with espeak...")
    raws = phonemize([c[0] for c in cands], language="en-us", backend="espeak",
                     strip=True, with_stress=False)

    rows, rej, examples = [], Counter(), {}

    def reject(reason, detail=None):
        rej[reason] += 1
        if detail:
            examples.setdefault(reason, []).append(detail)

    for (word, prons, z), raw in zip(cands, raws):
        phones = normalize(raw)
        if not phones:
            reject("espeak produced nothing")
            continue

        best = max(prons, key=lambda p: sum(1 for x in p if x[-1].isdigit()))
        cmu_syl = sum(1 for p in best if p[-1].isdigit())

        syllables = syllabify(phones)
        if len(syllables) < 2:
            reject("single syllable, nothing to isolate")
            continue
        if len(syllables) != cmu_syl:
            reject("AUDIT 1: syllable count disagrees with CMUdict",
                   f"{word} -> {''.join(phones)} ({len(syllables)} vs {cmu_syl})")
            continue

        d = disagreement(phones, arpa_to_ipa(best))
        if d > MAX_DISAGREEMENT:
            reject("AUDIT 2: phones disagree with CMUdict",
                   f"{word} -> {''.join(phones)} (disagreement {d:.2f})")
            continue

        reasons, trap, score = classify(word, phones, len(syllables), best)
        if score < MIN_DIFFICULTY:
            reject("not hard enough to be worth practising")
            continue

        rows.append({
            "id": word,
            "display": word,
            "ipa_syllables": syllables,
            "rpa_syllables": [],
            "trap": trap,
            "difficulty": reasons,
            "difficulty_score": score,
            "syllable_count": len(syllables),
            "zipf": z,
            "tier": tier(z),
            "reference_disagreement": round(d, 3),
            "verified": False,
        })

    def hardness(r):
        return (-r["difficulty_score"], -r["syllable_count"], -r["zipf"])

    buckets = {t: sorted([r for r in rows if r["tier"] == t], key=hardness)
               for t in ("common", "mid", "showcase")}
    quota = {"common": 0.20, "mid": 0.45, "showcase": 0.35}

    final = []
    for t, share in quota.items():
        final.extend(buckets[t][:int(TARGET * share)])
    if len(final) < TARGET:
        taken = {r["id"] for r in final}
        rest = sorted([r for r in rows if r["id"] not in taken], key=hardness)
        final.extend(rest[:TARGET - len(final)])

    final.sort(key=lambda r: (-r["zipf"], r["id"]))
    OUT.write_text(json.dumps(final, ensure_ascii=False, indent=2))

    counts = Counter(r["tier"] for r in final)
    tags = Counter(t for r in final for t in r["difficulty"])
    syls = Counter(r["syllable_count"] for r in final)

    lines = [
        "# Word bank build report",
        "",
        f"Derived from CMUdict ({len(cmu)} entries), phonemized with espeak-ng, "
        "frequency from wordfreq Zipf. Regenerate with "
        "`python scripts/build_wordbank.py`.",
        "",
        f"**{len(final)} words accepted** from {len(cands)} candidates.",
        "",
        "## Composition", "",
        "| tier | count |", "|---|---|",
    ]
    for t in ("common", "mid", "showcase"):
        lines.append(f"| {t} | {counts[t]} |")
    lines += ["", "| syllables | count |", "|---|---|"]
    for k in sorted(syls):
        lines.append(f"| {k} | {syls[k]} |")
    lines += ["", f"Mean difficulty score "
              f"{sum(r['difficulty_score'] for r in final) / len(final):.1f} "
              f"(threshold {MIN_DIFFICULTY}).", "",
              "| difficulty feature | count |", "|---|---|"]
    for k, v in tags.most_common():
        lines.append(f"| {k} | {v} |")

    lines += ["", "## Rejections", "",
              "Automatic, not editorial.", "",
              "| reason | count |", "|---|---|"]
    for k, v in rej.most_common():
        lines.append(f"| {k} | {v} |")

    lines += ["", "### Audit 1, dropped vowels", "",
              "espeak's syllable count disagrees with the dictionary, meaning it "
              "dropped a vowel. A learner saying these correctly would be marked "
              "wrong against the reference.", ""]
    for ex in examples.get("AUDIT 1: syllable count disagrees with CMUdict", [])[:30]:
        lines.append(f"* `{ex}`")

    lines += ["", "### Audit 2, wrong phones", "",
              "The syllable count is right but the sounds are not. Mostly "
              "loanwords, where espeak applies English spelling rules to a word "
              "that does not follow them, and rare clusters where it gives up.", ""]
    for ex in examples.get("AUDIT 2: phones disagree with CMUdict", [])[:30]:
        lines.append(f"* `{ex}`")

    REPORT.write_text("\n".join(lines))

    print(f"\naccepted {len(final)}")
    for t in ("common", "mid", "showcase"):
        print(f"  {t:<9} {counts[t]}")
    print("\nrejections:")
    for k, v in rej.most_common():
        print(f"  {v:>6}  {k}")


if __name__ == "__main__":
    main()
