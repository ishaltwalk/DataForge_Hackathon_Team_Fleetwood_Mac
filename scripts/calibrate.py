"""Set the two scoring thresholds from labelled recordings.

The thresholds in core/score.py are placeholders. This script replaces guessing
with measurement, and produces evidence/calibration.md, which is the answer to
the question a technical judge will ask: how do you know your scoring works.

HOW TO RECORD
-------------
Pick 5 words from data/words.json. For each, record two clean attempts and two
deliberately wrong ones using that word's trap (for "thoroughly", say
"soroughly"). 20 clips total, about 20 minutes.

Name them so the label is in the filename:

    evidence/clips/calibration/thoroughly__clean__1.wav
    evidence/clips/calibration/thoroughly__wrong__1.wav

Then:

    python scripts/calibrate.py

READING THE OUTPUT
------------------
You want two separated clusters: clean clips scoring high with low worst_cost,
wrong clips scoring low with high worst_cost. The script prints the gap and
suggests thresholds in the middle of it.

If the clusters OVERLAP, do not fudge the thresholds. Overlap means something
upstream is broken, almost always phone normalization or audio quality. Go back
and re-run the reference-vs-ASR comparison for one word before touching this.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
CLIPS = ROOT / "evidence" / "clips" / "calibration"
BANK = ROOT / "data" / "words.json"
REPORT = ROOT / "evidence" / "calibration.md"

NAME = re.compile(r"^(?P<word>[^_]+)__(?P<label>clean|wrong)__(?P<n>\d+)\.wav$")


def collect():
    from core.asr import transcribe
    from core.score import score

    bank = {e["id"]: e for e in json.loads(BANK.read_text())}
    rows = []

    clips = sorted(CLIPS.glob("*.wav"))
    if not clips:
        sys.exit(f"no clips found in {CLIPS}. See the docstring for naming.")

    for path in clips:
        m = NAME.match(path.name)
        if not m:
            print(f"  skipping {path.name}, name does not match the pattern")
            continue
        word, label = m["word"], m["label"]
        if word not in bank:
            print(f"  skipping {path.name}, '{word}' is not in the word bank")
            continue

        heard = transcribe(str(path))
        r = score(bank[word], heard)
        rows.append({
            "clip": path.name,
            "word": word,
            "label": label,
            "status": r["status"],
            "score": r["score"],
            "worst_syllable": r["worst_syllable"],
            "worst_cost": r.get("worst_cost", 0.0),
            "heard": "".join(heard),
        })
    return rows


def suggest(rows):
    clean = [r for r in rows if r["label"] == "clean" and r["status"] == "ok"]
    wrong = [r for r in rows if r["label"] == "wrong" and r["status"] == "ok"]
    if not clean or not wrong:
        return None, None, "not enough usable clips in both classes"

    lo_clean = min(r["score"] for r in clean)
    hi_wrong = max(r["score"] for r in wrong)
    hi_clean_cost = max(r["worst_cost"] for r in clean)
    lo_wrong_cost = min(r["worst_cost"] for r in wrong)

    notes = []
    if lo_clean > hi_wrong:
        pass_t = round((lo_clean + hi_wrong) / 2, 3)
        notes.append(f"score gap: {hi_wrong} to {lo_clean}")
    else:
        pass_t = None
        notes.append(
            f"SCORE CLUSTERS OVERLAP (worst clean {lo_clean} <= best wrong {hi_wrong}). "
            "Do not pick a threshold. Check phone normalization and audio quality first."
        )

    if lo_wrong_cost > hi_clean_cost:
        syl_t = round((lo_wrong_cost + hi_clean_cost) / 2, 3)
        notes.append(f"syllable-cost gap: {hi_clean_cost} to {lo_wrong_cost}")
    else:
        syl_t = None
        notes.append(
            f"SYLLABLE-COST CLUSTERS OVERLAP (clean up to {hi_clean_cost}, "
            f"wrong from {lo_wrong_cost})."
        )

    return pass_t, syl_t, "; ".join(notes)


def main():
    rows = collect()
    pass_t, syl_t, notes = suggest(rows)

    header = "| clip | word | label | score | worst syl | worst cost | heard |"
    sep = "|---|---|---|---|---|---|---|"
    body = [
        f"| {r['clip']} | {r['word']} | {r['label']} | {r['score']} | "
        f"{r['worst_syllable']} | {r['worst_cost']} | `{r['heard']}` |"
        for r in sorted(rows, key=lambda r: (r["word"], r["label"]))
    ]

    md = "\n".join([
        "# Scoring calibration",
        "",
        f"{len(rows)} labelled clips. Clean attempts and deliberate "
        "mispronunciations of the same words, scored by the same pipeline used "
        "at runtime.",
        "",
        header, sep, *body,
        "",
        "## Result",
        "",
        notes,
        "",
        f"PASS_THRESHOLD = {pass_t}" if pass_t else "PASS_THRESHOLD: not set, clusters overlap",
        "",
        f"SYL_THRESHOLD = {syl_t}" if syl_t else "SYL_THRESHOLD: not set, clusters overlap",
        "",
        "Reproduce with `python scripts/calibrate.py` against the committed clips.",
    ])

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(md)
    print(md)
    print(f"\nwrote {REPORT}")
    if pass_t and syl_t:
        print(f"\nNow set these in core/score.py:\n  PASS_THRESHOLD = {pass_t}\n  SYL_THRESHOLD = {syl_t}")


if __name__ == "__main__":
    main()
