"""Turn "syllable 2 was wrong" into a Rime request.

Owned by the Rime track.

REVISION NOTE -- read this before touching the constants below.

The original design here escalated correction across three attempts (whole
word slowed, syllables paused apart, isolated syllable alone) and flagged one
open question: whether inlineSpeedAlpha's [] nests correctly around a
phonemized {} chunk, since Rime's docs never demo the two together.

Both things got resolved by actually listening through Rime, not by reading
the docs further:

  * The nesting works. [{0xm}] correctly phonemizes AND slows just that
    chunk. Confirmed live (agricultural, culture, picture -- see git history
    around the RPA affricate fix for the specific test).
  * <N> pauses between chunks make it sound worse, not clearer. Tested with
    several gap values; dropped entirely rather than tuned.

So the three-attempt escalation is gone. There's one correction shape now:
every syllable plays as its own {rpa} chunk, '-' joins them (required syntax
for multi-chunk RPA, not a pause -- see RIME_EVIDENCE.md), and whichever
syllable(s) were actually wrong get [] around them so inlineSpeedAlpha slows
only those. If every syllable was wrong, every chunk is bracketed -- that
falls out of the same rule, it isn't a special case.

    {k1Ast}-[{0xm}]              one wrong syllable
    [{k1Ast}]-[{0xm}]            both wrong

Every correction still goes out as speech, never as readable IPA on screen.
That's unchanged and non-negotiable -- see the brief's eligibility clause on
what counts as voice actually being necessary.
"""

INLINE_SPEED = "1.3"


def wrong_syllables(syllable_costs: list[float], threshold: float) -> set[int]:
    """Which syllable indices exceed the per-syllable cost threshold.

    Use the same threshold core/score.py uses to decide `passed`, so
    "wrong enough to highlight" means the same thing in scoring and in the
    correction it triggers.

    Can return more than one index, or all of them. If none individually
    clear the threshold but the caller already knows the attempt failed
    overall, falls back to the single highest-cost syllable so the learner
    still has something to listen for.
    """
    flagged = {i for i, cost in enumerate(syllable_costs) if cost > threshold}
    if flagged:
        return flagged
    return {max(range(len(syllable_costs)), key=lambda i: syllable_costs[i])}


def build_correction(entry: dict, wrong_indices: set[int]) -> dict:
    """Keyword arguments for the Rime synthesize() call.

    entry           a data/words.json record
    wrong_indices   syllable indices to bracket + slow, from wrong_syllables()
    """
    chunks = entry["rpa_syllables"]
    assert chunks, f"{entry['id']} has no RPA syllables"

    parts = []
    for i, syl in enumerate(chunks):
        chunk = "{" + syl + "}"
        if i in wrong_indices:
            chunk = "[" + chunk + "]"
        parts.append(chunk)

    return {
        "text": "-".join(parts),
        "phonemize_brackets": True,
        "pause_brackets": False,
        "inline_speed": INLINE_SPEED,
    }


def build_prompt(entry: dict) -> dict:
    """The model pronunciation played before the user's first attempt.

    Nothing is bracketed here, so it's one plain {} chunk rather than
    dash-joined pieces -- there's no reason to split it when nothing needs
    an individual speed override.
    """
    return {
        "text": "{" + "".join(entry["rpa_syllables"]) + "}",
        "phonemize_brackets": True,
        "pause_brackets": False,
    }


def coaching_line(entry: dict, wrong_indices: set[int]) -> str:
    """Spoken, never printed alone. See the note about readable corrections."""
    if not wrong_indices:
        return "I did not hear anything that time."
    ordinal = ["first", "second", "third", "fourth", "fifth", "sixth"]
    names = [ordinal[i] if i < len(ordinal) else "last" for i in sorted(wrong_indices)]
    if len(names) == 1:
        return f"The {names[0]} syllable is the one to fix."
    return f"The {', '.join(names[:-1])} and {names[-1]} syllables need work."
