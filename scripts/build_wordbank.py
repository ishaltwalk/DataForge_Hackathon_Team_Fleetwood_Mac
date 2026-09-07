"""Build the IPA half of data/words.json.

Semi-manual on purpose. Ten words is an hour of hand-splitting; writing a
syllabifier that works on espeak output is a day and would still be wrong on
exactly the hard words this app is built around.

Usage:
    python scripts/build_wordbank.py            # interactive
    python scripts/build_wordbank.py --dump     # just print the phones

For each word it prints the espeak phone sequence with indices. You type the
split points as space-separated syllable groups using those indices, e.g.

    thoroughly -> 0:u03b8  1:u028c  2:u0279  3:o  4:u028a  5:l  6:i
    split: 0-1 2-4 5-6

Splits must match the syllable boundaries used in the RPA column, or the
correction step will enunciate the wrong syllable.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.g2p import espeak_phones, espeak_version  # noqa: E402

BANK = Path(__file__).resolve().parent.parent / "data" / "words.json"

# Candidate words. Every one is multisyllabic and carries a known trap.
# Single-syllable words are excluded: they give the syllable-isolation feature
# nothing to isolate.
CANDIDATES = [
    ("thoroughly", "u03b8 vs s"),
    ("something", "u03b8 vs t/f"),
    ("strengthen", "u03b8 vs t, plus cluster"),
    ("algorithm", "u03b8 vs t, plus stress"),
    ("authority", "u03b8 vs t"),
    ("parallel", "u0279 vs l, twice"),
    ("regularly", "u0279 vs l"),
    ("reliable", "u0279 vs l"),
    ("vulnerable", "v vs w, plus u0279/l"),
    ("available", "v vs w"),
    ("statistics", "cluster, stress"),
    ("specifically", "cluster, stress"),
]


def dump():
    print(f"# espeak-ng version {espeak_version()}\n")
    for word, trap in CANDIDATES:
        phones = espeak_phones(word)
        indexed = "  ".join(f"{i}:{p}" for i, p in enumerate(phones))
        print(f"{word:<16} ({trap})")
        print(f"    {indexed}")
        print(f"    flat: {''.join(phones)}  [{len(phones)} segments]\n")


def parse_split(spec: str, phones: list[str]) -> list[list[str]]:
    """'0-1 2-4 5-6' -> [[p0,p1],[p2,p3,p4],[p5,p6]]"""
    syllables = []
    for group in spec.split():
        if "-" in group:
            lo, hi = group.split("-")
            syllables.append(phones[int(lo): int(hi) + 1])
        else:
            syllables.append([phones[int(group)]])
    covered = sum(len(s) for s in syllables)
    if covered != len(phones):
        raise ValueError(f"split covers {covered} of {len(phones)} segments")
    return syllables


def interactive():
    bank = json.loads(BANK.read_text()) if BANK.exists() else []
    by_id = {e["id"]: e for e in bank}

    for word, trap in CANDIDATES:
        phones = espeak_phones(word)
        print(f"\n{word}  ({trap})")
        print("  " + "  ".join(f"{i}:{p}" for i, p in enumerate(phones)))
        spec = input("  split (blank to skip): ").strip()
        if not spec:
            continue
        try:
            syllables = parse_split(spec, phones)
        except (ValueError, IndexError) as exc:
            print(f"  rejected: {exc}")
            continue

        entry = by_id.get(word, {"id": word, "display": word, "rpa_syllables": []})
        entry["ipa_syllables"] = syllables
        entry["trap"] = trap
        by_id[word] = entry
        print("  ok: " + " / ".join("".join(s) for s in syllables))

    out = list(by_id.values())
    BANK.parent.mkdir(exist_ok=True)
    BANK.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nwrote {len(out)} entries to {BANK}")


if __name__ == "__main__":
    if "--dump" in sys.argv:
        dump()
    else:
        interactive()
