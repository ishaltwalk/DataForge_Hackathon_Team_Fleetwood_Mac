"""The 20-minute check that protects the rest of the build. Run this first.

Both sides of the comparison claim to produce "espeak phones". If they quietly
disagree (length marks on one side only, u0279 vs r, diphthongs split
differently, stress digits surviving), every distance in the system becomes
meaningless while still looking like plausible numbers. That failure is
indistinguishable from "the model is bad" and it can eat a whole day.

    python scripts/sanity_check.py evidence/clips/sanity/thoroughly.wav thoroughly

Record yourself saying the word clearly and correctly. If the two rows below do
not match, or match only loosely, fix core/phones.py before writing another
line of scoring code. Do not proceed. Do not tune thresholds.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.align import align, describe  # noqa: E402
from core.g2p import espeak_phones  # noqa: E402


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    wav, word = sys.argv[1], sys.argv[2]

    from core.asr import transcribe

    ref = espeak_phones(word)
    hyp = transcribe(wav)

    print(f"\nword: {word}\n")
    print(f"  espeak reference : {' '.join(ref)}")
    print(f"  asr output       : {' '.join(hyp)}")

    total, ops = align(ref, hyp)
    print(f"\n  diff  : {describe(ops)}")
    print(f"  cost  : {total:.3f} over {len(ref)} phones")

    subs = [o for o in ops if o[0] == "sub"]
    drops = [o for o in ops if o[0] in ("del", "ins")]

    print("\n" + "-" * 60)
    if total == 0:
        print("  PERFECT MATCH. Both sides share a phone inventory. Proceed.")
    elif len(drops) > len(ref) // 2:
        print("  BAD. More than half the phones failed to align at all.")
        print("  This is almost certainly a normalization mismatch, not bad")
        print("  pronunciation. Compare the two rows above symbol by symbol")
        print("  and fix core/phones.py. Do NOT proceed to scoring.")
    elif len(subs) > len(ref) // 3:
        print("  SUSPICIOUS. A third of the phones were substituted on a clip")
        print("  you believe is correct. Check for r/u0279, length marks, and")
        print("  diphthong handling before proceeding.")
    else:
        print("  CLOSE ENOUGH. A couple of differences on a real recording is")
        print("  normal. Both sides are speaking the same alphabet. Proceed.")
    print("-" * 60 + "\n")


if __name__ == "__main__":
    main()
