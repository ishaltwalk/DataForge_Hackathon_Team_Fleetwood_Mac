"""Turn "syllable 2 was wrong" into a Rime request.

Owned by the Rime track. Written against the score() contract so it can be
wired up the moment the scorer lands.

The escalation matters. Replaying identical audio after a failed attempt
teaches nothing, so each retry isolates the problem further:

    attempt 1   whole word, correct phonemes, slightly slowed
    attempt 2   syllables separated by pauses, the wrong one slowed
    attempt 3+  the wrong syllable alone, then the whole word again

Every correction goes out as speech. None of it is rendered as readable IPA on
screen. That is deliberate: if the user could read the fix, removing the voice
would leave the product intact, which is the thing the brief explicitly says is
not enough.


THE ONE UNVERIFIED ASSUMPTION
-----------------------------
Attempts 2 and 3 nest inlineSpeedAlpha's square brackets around custom
pronunciation's curly braces: [{t0xm}]. Rime's docs demo the two features
separately and never together, so this needs a live test before it is trusted:

    text: "{k1As}<300>[{t0xm}]"
    phonemizeBetweenBrackets: true
    pauseBetweenBrackets: true
    inlineSpeedAlpha: "1.8"

If the pause works but the speed on the bracketed chunk is ignored, or the
parser chokes, set NEST_SPEED_IN_PHONEME = False. The syllable isolation still
works, the speed just applies to the whole utterance instead. Slightly less
precise, still a working product. Record whichever branch shipped in the README
under failure behavior, because disclosed fallbacks are allowed and undisclosed
ones are not.
"""

# Flip to False if the [{ }] nesting test fails. See the docstring.
NEST_SPEED_IN_PHONEME = True

# Pause between isolated syllables, milliseconds. 300 is long enough to hear as
# a break without sounding broken.
SYLLABLE_PAUSE_MS = 300

# Mist v3 treats values above 1.0 as slower. Rime's own guidance is to move up
# gradually rather than jumping straight to an aggressive value, because
# naturalness degrades before intelligibility does.
SPEED_GENTLE = "1.4"
SPEED_SLOW = "1.8"
SPEED_SLOWEST = "2.0"


def _chunk(rpa: str, slow: bool) -> str:
    if slow and NEST_SPEED_IN_PHONEME:
        return "[{" + rpa + "}]"
    return "{" + rpa + "}"


def build_correction(entry: dict, worst_syllable: int, attempt: int) -> dict:
    """Keyword arguments for the Rime synthesize() call.

    entry           a data/words.json record
    worst_syllable  index from score(), or None when nothing was heard
    attempt         1-based count of failed attempts so far
    """
    chunks = entry["rpa_syllables"]
    assert chunks, f"{entry['id']} has no RPA syllables"

    if worst_syllable is None:
        return {
            "text": "I did not catch that. Listen again. {" + "".join(chunks) + "}",
            "phonemize_brackets": True,
            "pause_brackets": False,
            "inline_speed": SPEED_GENTLE,
        }

    if attempt <= 1:
        # Whole word, correct phonemes guaranteed, gently slowed. Safe on every
        # verified feature, so this is the fallback if anything else misbehaves.
        return {
            "text": "Listen again. {" + "".join(chunks) + "}",
            "phonemize_brackets": True,
            "pause_brackets": False,
            "inline_speed": SPEED_GENTLE,
        }

    if attempt == 2:
        parts = [_chunk(c, slow=(i == worst_syllable)) for i, c in enumerate(chunks)]
        return {
            "text": "Break it down. " + f"<{SYLLABLE_PAUSE_MS}>".join(parts),
            "phonemize_brackets": True,
            "pause_brackets": True,
            "inline_speed": SPEED_SLOW,
        }

    bad = _chunk(chunks[worst_syllable], slow=True)
    whole = "{" + "".join(chunks) + "}"
    return {
        "text": f"Just this part. {bad}<400>Now the whole word. {whole}",
        "phonemize_brackets": True,
        "pause_brackets": True,
        "inline_speed": SPEED_SLOWEST,
    }


def build_prompt(entry: dict) -> dict:
    """The model pronunciation played before the user's first attempt."""
    return {
        "text": "{" + "".join(entry["rpa_syllables"]) + "}",
        "phonemize_brackets": True,
        "pause_brackets": False,
        "inline_speed": None,
    }


def coaching_line(entry: dict, worst_syllable: int) -> str:
    """Spoken, never printed alone. See the note about readable corrections."""
    if worst_syllable is None:
        return "I did not hear anything that time."
    ordinal = ["first", "second", "third", "fourth", "fifth"]
    which = ordinal[worst_syllable] if worst_syllable < len(ordinal) else "last"
    return f"The {which} syllable is the one to fix."
