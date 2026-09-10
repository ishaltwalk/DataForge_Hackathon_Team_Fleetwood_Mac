from dataclasses import dataclass, field

from core import correct
from core.align import describe
from core.score import SYL_THRESHOLD, score
from core.session import Session
from core.speech import Spoken, speak


@dataclass
class Turn:
    state: str
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
    result = score(entry, heard)
    state = sess.submit(result)

    if state == "no_speech":
        return Turn(state=state, result=result, attempts=sess.attempts)

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
        turn.spoken = speak(**correct.build_prompt(entry))
        return turn

    if not wrong:
        turn.coaching = "Close. Listen to the whole word once more."
        turn.spoken = speak(**correct.build_prompt(entry))
        return turn

    turn.coaching = correct.coaching_line(entry, wrong)
    turn.spoken = speak(**correct.build_correction(entry, wrong))
    return turn


def prompt(entry: dict) -> Spoken:
    return speak(**correct.build_prompt(entry))
