"""One attempt, start to finish. Both front ends call this and nothing else.

The Streamlit app and the Flask API each used to run their own version of this
sequence: score, decide which syllables were wrong, build a payload, speak it.
Four steps, two copies, and they had already diverged on step two (one used
`worst_syllable`, the other used the threshold set). The result was a demo
where the highlighted syllable and the spoken syllable were different sounds,
which is the single worst bug this product can have, because it is invisible
in code review and obvious to a judge wearing headphones.

So the sequence lives here once. A front end may decide how to draw a Turn.
It may not decide what a Turn contains.
"""

from dataclasses import dataclass, field

from core import correct
from core.align import describe
from core.score import SYL_THRESHOLD, score
from core.session import Session
from core.speech import Spoken, speak


@dataclass
class Turn:
    state: str                      # no_speech | pass | retry | give_up
    result: dict
    wrong: set[int] = field(default_factory=set)
    coaching: str | None = None
    spoken: Spoken | None = None
    attempts: int = 0
    changed_syllable: bool = False

    @property
    def diff(self) -> str:
        return describe(self.result["ops"])


def take_turn(entry: dict, heard: list[str], sess: Session) -> Turn:
    """Score one attempt and produce the spoken response it earns."""
    result = score(entry, heard)
    state = sess.submit(result)

    if state == "no_speech":
        # No audio at all. Do not score it, do not correct it, and do not
        # burn an attempt: Session.submit already declined to record it.
        return Turn(state=state, result=result, attempts=sess.attempts)

    # Computed ONCE and reused for the on-screen highlight and the spoken
    # correction. Two call sites is how they drift apart.
    wrong = (
        set()
        if result["passed"]
        else correct.wrong_syllables(result["syllable_costs"], SYL_THRESHOLD)
    )

    turn = Turn(
        state=state,
        result=result,
        wrong=wrong,
        attempts=sess.attempts,
        changed_syllable=sess.moved_on() and sess.attempts > 1,
    )

    if state == "pass":
        return turn

    if state == "give_up":
        # Out of attempts. One clean model pronunciation, no bracketing.
        turn.spoken = speak(**correct.build_prompt(entry))
        return turn

    if not wrong:
        # Failed the overall gate but no syllable is individually blameable
        # (a diffuse miss, or a very short word). Replaying the whole word is
        # honest; inventing a syllable to blame is not.
        turn.coaching = "Close. Listen to the whole word once more."
        turn.spoken = speak(**correct.build_prompt(entry))
        return turn

    turn.coaching = correct.coaching_line(entry, wrong)
    turn.spoken = speak(**correct.build_correction(entry, wrong))
    return turn


def prompt(entry: dict) -> Spoken:
    """The model pronunciation, played before the first attempt."""
    return speak(**correct.build_prompt(entry))
