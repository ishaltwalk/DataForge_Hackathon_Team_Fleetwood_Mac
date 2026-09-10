"""Render the A/B pairs that prove the Rime controls are doing the work.

    python scripts/ab_clips.py

Needs RIME_API_KEY. Writes into evidence/clips/ab/ and prints a table for
RIME_EVIDENCE.md sections 4.4 to 4.6.

WHY THIS IS A SCRIPT AND NOT A PARAGRAPH
----------------------------------------
The brief asks for prompting and delivery claims to be proved by holding the
model and voice constant, rendering at least two variants, saving the clips,
and explaining which change altered the result. A paragraph asserting that
`phonemizeBetweenBrackets` matters is worth nothing; two clips of the same word
from the same voice, one of which says it correctly and one of which does not,
is the whole argument.

Model and speaker are read from rime_tts.synthesize so they cannot drift from
the judged path. If the app ships mistv3/falcon, these clips are mistv3/falcon.

THREE PAIRS, EACH ISOLATING ONE VARIABLE
----------------------------------------
4.4  plain text  vs  {RPA} with phonemizeBetweenBrackets
     Same word, same voice. Only the bracket control changes. On a word
     outside Rime's dictionary the plain render is the model's own G2P guess,
     which for this bank is frequently the exact mispronunciation being
     corrected. This is the pair that justifies the whole reference library.

4.5  whole word slowed  vs  one syllable slowed in place
     Same word, same voice, same inlineSpeedAlpha value. Only the bracketing
     changes. Slowing everything is not a correction, it is a slow word; the
     claim is that isolating one syllable inside a normal-speed word is what
     makes the error audible.

4.6  the same correction at several speeds
     One variable, the alpha value. Listen and rate intelligibility and
     naturalness. The shipped value is INLINE_SPEED in core/correct.py and
     this is the evidence for choosing it rather than guessing.

Listening is the measurement here and it is not automatable. The script gets
the clips onto disk with honest filenames; a human still has to put headphones
on and write down what they heard.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.correct import INLINE_SPEED, build_correction, build_prompt  # noqa: E402
from rime_tts.synthesize import (  # noqa: E402
    DEFAULT_SPEAKER,
    LANGUAGE,
    MODEL_ID,
    RimeError,
    save,
    synthesize,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "evidence" / "clips" / "ab"
BANK = ROOT / "data" / "words.json"

# Words that are in the bank, multi-syllable, and outside the everyday
# vocabulary a TTS dictionary is likely to cover. The point of 4.4 collapses
# on a word Rime already knows how to say.
WORDS = ["ornithological", "coloratura", "equiangular"]

SPEEDS = ["1.0", "1.3", "1.6"]


def render(label: str, filename: str, **payload) -> str | None:
    """One Rime call, one file, one row of the table."""
    try:
        audio = synthesize(
            payload.pop("text"),
            speaker=DEFAULT_SPEAKER,
            **payload,
        )
    except RimeError as exc:
        print(f"  FAILED  {label}: {exc}")
        return None

    path = OUT / filename
    save(audio, str(path))
    print(f"  {len(audio):>7} bytes  {filename}")
    return filename


def main() -> None:
    import json

    OUT.mkdir(parents=True, exist_ok=True)
    bank = {e["id"]: e for e in json.loads(BANK.read_text(encoding="utf-8"))}

    missing = [w for w in WORDS if w not in bank]
    if missing:
        sys.exit(f"not in the word bank: {missing}")

    print(f"model {MODEL_ID} / speaker {DEFAULT_SPEAKER} / lang {LANGUAGE}")
    print("held constant across every clip below.\n")

    rows_44, rows_45, rows_46 = [], [], []

    for word in WORDS:
        entry = bank[word]
        print(f"{word}")

        # --- 4.4 plain text vs phonemized RPA -------------------------------
        # The ONLY difference is the bracket control. Same word, same voice.
        a = render(
            f"{word} plain",
            f"{word}_plain.wav",
            text=entry["display"],
        )
        b = render(
            f"{word} rpa",
            f"{word}_rpa.wav",
            **build_prompt(entry),
        )
        if a and b:
            rows_44.append((word, a, b))

        # --- 4.5 whole word slowed vs one syllable slowed -------------------
        # Same alpha value in both. Only the bracketing moves.
        whole = "[" + "{" + "".join(entry["rpa_syllables"]) + "}" + "]"
        a = render(
            f"{word} whole word slowed",
            f"{word}_wholeword.wav",
            text=whole,
            phonemize_brackets=True,
            inline_speed=INLINE_SPEED,
        )
        # Blame the middle syllable: a first or last syllable is easier to
        # hear in isolation and would flatter the result.
        middle = {len(entry["rpa_syllables"]) // 2}
        b = render(
            f"{word} syllable {sorted(middle)[0]} slowed in place",
            f"{word}_syllable.wav",
            **build_correction(entry, middle),
        )
        if a and b:
            rows_45.append((word, sorted(middle)[0], a, b))

        print()

    # --- 4.6 speed sweep on one word ---------------------------------------
    # One variable. Everything else identical to the shipped correction.
    sweep_word = WORDS[0]
    entry = bank[sweep_word]
    middle = {len(entry["rpa_syllables"]) // 2}
    payload = build_correction(entry, middle)
    print(f"speed sweep on {sweep_word}, syllable {sorted(middle)[0]}")
    for alpha in SPEEDS:
        name = render(
            f"alpha {alpha}",
            f"{sweep_word}_speed_{alpha.replace('.', '_')}.wav",
            **{**payload, "inline_speed": alpha},
        )
        if name:
            rows_46.append((alpha, name))

    # --- tables to paste into RIME_EVIDENCE.md ------------------------------
    print("\n" + "=" * 68)
    print("Paste into evidence/RIME_EVIDENCE.md, then listen and fill the")
    print("last column. The clips are the evidence; the words you write next")
    print("to them are the finding.")
    print("=" * 68)

    print("\n### 4.4 Custom pronunciation changes the output\n")
    print(f"Model `{MODEL_ID}`, speaker `{DEFAULT_SPEAKER}`, held constant.")
    print("Only `phonemizeBetweenBrackets` differs.\n")
    print("| Word | Clip | Sent as | What it said |")
    print("|---|---|---|---|")
    for word, plain, rpa in rows_44:
        print(f"| {word} | `ab/{plain}` | plain text | |")
        print(f"| {word} | `ab/{rpa}` | `{{RPA}}` phonemized | |")

    print("\n### 4.5 Syllable isolation changes the correction\n")
    print(f"Same word, same voice, `inlineSpeedAlpha` = {INLINE_SPEED} in both.")
    print("Only the bracketing differs.\n")
    print("| Word | Clip | Strategy | Was the error audible |")
    print("|---|---|---|---|")
    for word, idx, whole, syl in rows_45:
        print(f"| {word} | `ab/{whole}` | whole word slowed | |")
        print(f"| {word} | `ab/{syl}` | syllable {idx} slowed in place | |")

    print("\n### 4.6 Speed is intelligible and natural at the value shipped\n")
    print(f"`{sweep_word}`, one syllable, alpha swept. Shipped value is "
          f"{INLINE_SPEED}.\n")
    print("| Alpha | Clip | Intelligibility 1-5 | Naturalness 1-5 |")
    print("|---|---|---|---|")
    for alpha, name in rows_46:
        print(f"| {alpha} | `ab/{name}` | | |")

    print(f"\n{len(list(OUT.glob('*.wav')))} clips in {OUT.relative_to(ROOT)}")
    print("These commit: .gitignore excludes *.wav but re-includes")
    print("evidence/clips/**. Check `git status` shows them.")


if __name__ == "__main__":
    main()
