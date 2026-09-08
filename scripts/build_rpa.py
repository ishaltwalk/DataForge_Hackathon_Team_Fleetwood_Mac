"""Fill rpa_syllables into words.json.

Reuses ipa_syllables already in the bank (verified against CMUdict by
build_wordbank.py) instead of recording and /phonemize-ing 5000 words.
Stress comes from CMUdict too, since it's already the source of truth this
bank was audited against -- one less place for the reference to drift.

Run:  python scripts/build_rpa.py
Writes: data/words.json (in place), evidence/rpa_report.md
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cmudict

from core.rpa import UNMAPPED, word_to_rpa

WORDS_PATH = Path(__file__).resolve().parent.parent / "data" / "words.json"
REPORT_PATH = Path(__file__).resolve().parent.parent / "evidence" / "rpa_report.md"

_cmu = cmudict.dict()


def best_pron(word: str):
    """Same selection rule build_wordbank.py used for the syllable-count audit:
    the pronunciation variant with the most stress-bearing (i.e. vowel) slots.
    """
    prons = _cmu.get(word)
    if not prons:
        return None
    return max(prons, key=lambda p: sum(1 for x in p if x[-1].isdigit()))


def stress_digits(pron) -> list[str]:
    return [ph[-1] for ph in pron if ph[-1].isdigit()]


def main():
    data = json.loads(WORDS_PATH.read_text(encoding="utf-8"))

    ok, no_cmu, mismatched, unmapped_words = 0, [], [], []

    for entry in data:
        word = entry["id"]
        pron = best_pron(word)

        if pron is None:
            no_cmu.append(word)
            continue

        stresses = stress_digits(pron)
        if len(stresses) != len(entry["ipa_syllables"]):
            mismatched.append(word)
            continue

        before = len(UNMAPPED)
        entry["rpa_syllables"] = word_to_rpa(entry["ipa_syllables"], stresses)
        if len(UNMAPPED) > before:
            unmapped_words.append(word)
        else:
            ok += 1

    WORDS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    report = [
        "# RPA build report\n",
        f"**{ok} of {len(data)} words got rpa_syllables filled in.**\n",
        f"\n| issue | count |\n|---|---|\n"
        f"| no CMUdict entry (stress unknown) | {len(no_cmu)} |\n"
        f"| stress/syllable count mismatch | {len(mismatched)} |\n"
        f"| contained a symbol outside core/rpa.py's tables | {len(unmapped_words)} |\n",
    ]
    if UNMAPPED:
        report.append(f"\n## Unmapped symbols\n\n{sorted(UNMAPPED)}\n")
        report.append(f"Words hitting them: {unmapped_words}\n")
    if no_cmu:
        report.append(f"\n## No CMUdict entry\n\n{no_cmu}\n")
    if mismatched:
        report.append(f"\n## Stress/syllable mismatch\n\n{mismatched}\n")

    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text("".join(report), encoding="utf-8")

    print(f"ok {ok} / {len(data)}")
    print(f"no_cmu {len(no_cmu)}  mismatched {len(mismatched)}  unmapped {len(unmapped_words)}")
    if UNMAPPED:
        print("UNMAPPED SYMBOLS:", sorted(UNMAPPED))


if __name__ == "__main__":
    main()
