"""Measure the product claim at scale, with no recordings and no network.

    python scripts/attribution_study.py

Writes evidence/attribution.md.

WHY THIS EXISTS ALONGSIDE tests/acceptance.py
---------------------------------------------
acceptance.py is the honest end-to-end test: real microphone, real ASR, real
clips. It is also limited to however many clips a human was willing to record,
which is a dozen at best and says nothing about the other 4988 words.

This measures the same claim across the bank. It stubs exactly one thing, the
microphone, by constructing the phone sequence a speaker would produce if they
made a specific substitution in a specific syllable. Everything downstream of
that, the alignment, the articulatory distance, the syllable attribution and
the threshold, is the shipped code path.

So the two are complementary and neither replaces the other:

    acceptance.py         few clips, whole pipeline, proves it works on air
    attribution_study.py  whole bank, pipeline minus the mic, proves it scales

WHAT IS ACTUALLY BEING MEASURED
-------------------------------
Not "did it notice something was wrong". A tool that failed every attempt would
score 100% on that and be useless. The measurement is: given that the speaker
broke syllable N, did the product blame syllable N.

"Blame" means the set from core.correct.wrong_syllables, because that is the
set the UI highlights AND the set core.correct.build_correction brackets for
Rime. It is user-visible behaviour in the literal sense: it is the red box on
screen and the slowed syllable in the audio.

Three numbers come out, and the second is the one that matters:

    detection    of the sabotages, how many the pass gate caught at all
    precision    of the ones caught, how many named the right syllable
    false alarm  of the correct pronunciations, how many were failed anyway

Detection below 100% is under-sensitivity and is expected: a substitution one
articulatory feature wide is genuinely hard to hear, and core/score.py
documents that trade-off. Precision below 100% is the serious failure, because
it means the app confidently pointed at a syllable the speaker got right, and
Rime then enunciated the wrong thing. Those two are reported separately rather
than blended into one accuracy figure that would hide it.
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
BANK = ROOT / "data" / "words.json"
REPORT = ROOT / "evidence" / "attribution.md"

# Substitutions a real learner makes, not random phone swaps. Each is a
# documented L2 English difficulty: the dental fricatives, the liquids, the
# labiodental/glide confusion, the postalveolars, and the tense/lax vowel
# pairs. Random substitutions would inflate the result, because a phone chosen
# at random is usually far away in feature space and therefore easy to catch.
SUBSTITUTIONS = {
    "θ": "s", "ð": "z",          # think/sink, this/zis
    "ɹ": "l", "l": "ɹ",          # the liquid merge
    "v": "w", "w": "v",          # very/wery
    "ʃ": "s", "ʒ": "z",          # ship/sip
    "tʃ": "ʃ", "dʒ": "ʒ",        # chair/share
    "ŋ": "n",                     # sing/sin
    "æ": "ɛ", "ɛ": "æ",          # bad/bed
    "ɪ": "i", "i": "ɪ",          # ship/sheep
    "ʊ": "u", "u": "ʊ",          # full/fool
    "ə": "ʌ", "ʌ": "ɑ",          # unstressed vowel drift
    "z": "s", "s": "z",           # final devoicing
}


def sabotage(entry: dict, index: int) -> list[str] | None:
    """The phone sequence of this word with ONE phone changed in syllable
    `index`. Returns None when that syllable contains nothing substitutable,
    which is not a failure, just a syllable this method cannot test.

    Only the first eligible phone is changed. Breaking every phone in the
    syllable would make attribution trivially easy and the number meaningless.
    """
    out: list[str] = []
    changed = False
    for i, syllable in enumerate(entry["ipa_syllables"]):
        for phone in syllable:
            if i == index and phone in SUBSTITUTIONS and not changed:
                out.append(SUBSTITUTIONS[phone])
                changed = True
            else:
                out.append(phone)
    return out if changed else None


def run() -> dict:
    from core.correct import wrong_syllables
    from core.score import SYL_THRESHOLD, score, validate_bank

    bank = json.loads(BANK.read_text(encoding="utf-8"))
    validate_bank(bank)

    correct_phones = lambda e: [p for s in e["ipa_syllables"] for p in s]  # noqa: E731

    tested = caught = correct_blame = false_alarms = 0
    words_covered = 0
    by_syllable_count: Counter = Counter()
    caught_by_syllable_count: Counter = Counter()
    misattributed: list[tuple[str, int, list[int]]] = []
    missed: list[tuple[str, int, float]] = []

    for entry in bank:
        # Control first. A correct pronunciation must pass, or every sabotage
        # result for this word is meaningless.
        control = score(entry, correct_phones(entry))
        if not control["passed"]:
            false_alarms += 1
            continue

        n = len(entry["ipa_syllables"])
        touched = False

        for index in range(n):
            heard = sabotage(entry, index)
            if heard is None:
                continue

            touched = True
            tested += 1
            by_syllable_count[n] += 1

            result = score(entry, heard)
            if result["passed"]:
                # Under-sensitivity: the substitution was too small to trip
                # the gate. Recorded, not silently dropped.
                missed.append((entry["id"], index, result["score"]))
                continue

            caught += 1
            caught_by_syllable_count[n] += 1

            blamed = wrong_syllables(result["syllable_costs"], SYL_THRESHOLD)
            if index in blamed:
                correct_blame += 1
            else:
                misattributed.append((entry["id"], index, sorted(blamed)))

        words_covered += touched

    return {
        "bank_size": len(bank),
        "words_covered": words_covered,
        "tested": tested,
        "caught": caught,
        "correct_blame": correct_blame,
        "false_alarms": false_alarms,
        "missed": missed,
        "misattributed": misattributed,
        "by_syllable_count": by_syllable_count,
        "caught_by_syllable_count": caught_by_syllable_count,
        "threshold": SYL_THRESHOLD,
    }


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "n/a"


def write_report(r: dict) -> None:
    lines: list[str] = []
    add = lines.append

    add("# Syllable attribution study")
    add("")
    add("Generated by `python scripts/attribution_study.py`. No audio, no")
    add("network, no API keys. Deterministic: the same command produces the")
    add("same numbers on any machine with the repository checked out.")
    add("")
    add("## Method")
    add("")
    add("For every word in the committed bank, one phone in one syllable is")
    add("replaced with a substitution a real learner makes (th to s, r to l,")
    add("v to w, tense to lax vowels, and so on), one syllable at a time. The")
    add("resulting phone sequence is fed to the shipped scorer.")
    add("")
    add("Only the microphone is stubbed. The alignment, the articulatory")
    add("distance, the syllable attribution and the pass threshold are the")
    add("same code the running app uses. The blamed set is read from")
    add("`core.correct.wrong_syllables`, which is both what the UI highlights")
    add("and what `build_correction` brackets for Rime, so this measures")
    add("user-visible behaviour rather than an internal proxy.")
    add("")
    add("Each word is first scored on its correct pronunciation. A word that")
    add("fails its own control is excluded and counted as a false alarm,")
    add("because sabotage results for it would be meaningless.")
    add("")
    add("## Results")
    add("")
    add(f"Word bank: **{r['bank_size']} words**, of which "
        f"**{r['words_covered']}** contain at least one substitutable phone.")
    add(f"Per-syllable cost threshold: `{r['threshold']}`.")
    add("")
    add("| Measure | Count | Rate |")
    add("|---|---|---|")
    add(f"| Sabotages tested | {r['tested']} | |")
    add(f"| Detected as a failure | {r['caught']} | {pct(r['caught'], r['tested'])} |")
    add(f"| **Correct syllable blamed, of those detected** | "
        f"**{r['correct_blame']} / {r['caught']}** | "
        f"**{pct(r['correct_blame'], r['caught'])}** |")
    add(f"| Misattributed (blamed the wrong syllable) | {len(r['misattributed'])} | "
        f"{pct(len(r['misattributed']), r['caught'])} |")
    add(f"| Undetected (substitution too small to trip the gate) | {len(r['missed'])} | "
        f"{pct(len(r['missed']), r['tested'])} |")
    add(f"| False alarms on correct pronunciation | {r['false_alarms']} | "
        f"{pct(r['false_alarms'], r['bank_size'])} |")
    add("")
    add("### Reading these")
    add("")
    add("**The bolded row is the claim.** Detecting that something was wrong")
    add("is the easy half, and a tool that failed every attempt would score")
    add("100% on detection while being useless. The product claim is that the")
    add("syllable it points at is the syllable the speaker actually broke.")
    add("")
    add("**Undetected is under-sensitivity, and is the expected trade-off.** A")
    add("substitution one articulatory feature wide is genuinely close to the")
    add("target. `core/score.py` documents why the syllable-level gate carries")
    add("the pass decision rather than the overall score, and these are the")
    add("cases that sit just under it. They are counted here rather than")
    add("dropped, because a study that hid them would be measuring the wrong")
    add("thing.")
    add("")
    add("**Misattribution is the serious failure.** It means the app pointed")
    add("at a syllable the speaker got right, and Rime then enunciated the")
    add("wrong sound. That is why it is reported separately instead of being")
    add("blended into a single accuracy figure.")
    add("")
    add("### By word length")
    add("")
    add("| Syllables | Sabotages tested | Detected | Detection rate |")
    add("|---|---|---|---|")
    for n in sorted(r["by_syllable_count"]):
        t = r["by_syllable_count"][n]
        c = r["caught_by_syllable_count"][n]
        add(f"| {n} | {t} | {c} | {pct(c, t)} |")
    add("")

    if r["misattributed"]:
        add("### Every misattribution")
        add("")
        add("Listed in full rather than summarised. If this table is long, the")
        add("claim above is weaker than it looks and the reader should see why.")
        add("")
        add("| Word | Syllable broken | Syllable(s) blamed |")
        add("|---|---|---|")
        for word, broke, blamed in r["misattributed"][:60]:
            add(f"| `{word}` | {broke} | {blamed} |")
        if len(r["misattributed"]) > 60:
            add("")
            add(f"({len(r['misattributed']) - 60} further rows omitted for length.)")
        add("")
    else:
        add("### Misattributions")
        add("")
        add("None. Every detected sabotage named the syllable that was broken.")
        add("")

    add("## What this does not show")
    add("")
    add("This study starts from a phone sequence, so it does not exercise the")
    add("microphone, the browser's audio conversion, or Whisper. Those are")
    add("covered by `tests/acceptance.py`, which runs the whole path against")
    add("committed recordings. Read the two together: this one shows the")
    add("scoring generalises across the bank, that one shows it survives real")
    add("audio.")
    add("")
    add("It also assumes a learner substitutes one phone cleanly. Real")
    add("mispronunciation is messier: timing drifts, syllables get dropped")
    add("entirely, stress lands wrong. Dropped syllables cost far more than a")
    add("substitution and are correspondingly easier to attribute, so the")
    add("numbers here are the pessimistic end of the range rather than the")
    add("flattering one.")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    print("running attribution study over the committed word bank...")
    r = run()
    write_report(r)
    print(f"\n  sabotages tested        {r['tested']}")
    print(f"  detected                {r['caught']}  ({pct(r['caught'], r['tested'])})")
    print(f"  correct syllable blamed {r['correct_blame']}/{r['caught']}  "
          f"({pct(r['correct_blame'], r['caught'])})")
    print(f"  misattributed           {len(r['misattributed'])}")
    print(f"  false alarms            {r['false_alarms']}")
    print(f"\nwrote {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
