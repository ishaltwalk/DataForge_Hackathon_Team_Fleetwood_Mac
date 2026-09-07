"""Acceptance test. Defined before the demo, as the brief requires.

    python tests/acceptance.py

CLAIM UNDER TEST
----------------
The tool does not just detect that a word was mispronounced. It identifies
which syllable was wrong, and it is that identification the correction depends
on. "It failed" is a buzzer; "it failed and it pointed at the right syllable"
is the product.

So the assertion on a mispronounced clip is not `passed == False`. It is
`worst_syllable == the syllable containing the trap phoneme`. A tool that fails
everything would pass the first assertion and fail this one.

CLIPS
-----
    evidence/clips/acceptance/clean/<word>.wav          expect: pass
    evidence/clips/acceptance/wrong/<word>__<n>.wav     expect: fail, blame syllable n
    evidence/clips/acceptance/noisy/<word>.wav          expect: pass, or documented

The <n> in a wrong-clip filename is the syllable index the speaker deliberately
broke. Record them knowing which syllable you are sabotaging.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
CLIPS = ROOT / "evidence" / "clips" / "acceptance"
BANK = ROOT / "data" / "words.json"

WRONG_NAME = re.compile(r"^(?P<word>[^_]+)__(?P<syl>\d+)\.wav$")


def run():
    from core.asr import transcribe
    from core.score import score, validate_bank

    bank = json.loads(BANK.read_text())
    validate_bank(bank)
    by_id = {e["id"]: e for e in bank}

    rows, failures = [], 0

    # 1. Clean attempts should pass.
    for path in sorted((CLIPS / "clean").glob("*.wav")):
        word = path.stem
        if word not in by_id:
            continue
        r = score(by_id[word], transcribe(str(path)))
        ok = r["passed"]
        failures += not ok
        rows.append((path.name, "clean", "pass", "pass" if ok else "fail",
                     r["score"], r["worst_syllable"], ok))

    # 2. Mispronounced attempts should fail AND blame the right syllable.
    for path in sorted((CLIPS / "wrong").glob("*.wav")):
        m = WRONG_NAME.match(path.name)
        if not m or m["word"] not in by_id:
            continue
        expected = int(m["syl"])
        r = score(by_id[m["word"]], transcribe(str(path)))
        ok = (not r["passed"]) and r["worst_syllable"] == expected
        failures += not ok
        rows.append((path.name, "wrong", f"fail, blame {expected}",
                     f"{'fail' if not r['passed'] else 'pass'}, blame {r['worst_syllable']}",
                     r["score"], r["worst_syllable"], ok))

    # 3. Stress case: clean speech with background noise. Not a hard failure,
    #    because degrading under noise is a limitation to disclose, not a bug
    #    to hide. But it must be measured, not assumed.
    for path in sorted((CLIPS / "noisy").glob("*.wav")):
        word = path.stem
        if word not in by_id:
            continue
        r = score(by_id[word], transcribe(str(path)))
        rows.append((path.name, "noisy", "pass (documented if not)",
                     "pass" if r["passed"] else "fail",
                     r["score"], r["worst_syllable"], True))

    width = max((len(r[0]) for r in rows), default=10) + 2
    print(f"\n{'clip':<{width}}{'kind':<8}{'expected':<20}{'actual':<20}{'score':<8}ok")
    print("-" * (width + 60))
    for name, kind, exp, act, sc, _ws, ok in rows:
        print(f"{name:<{width}}{kind:<8}{exp:<20}{act:<20}{sc:<8}{'y' if ok else 'N'}")

    print(f"\n{len(rows)} clips, {failures} failures")
    return failures


if __name__ == "__main__":
    if not CLIPS.exists():
        sys.exit(f"no clips at {CLIPS}. See the docstring for the layout.")
    sys.exit(1 if run() else 0)
