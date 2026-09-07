"""Attempt loop for one word.

Small on purpose. The only real decisions here are when to stop and what to
notice across attempts.

Stopping matters. A loop with no exit is a bad demo and a worse product: a
learner who cannot produce a sound after four tries needs to move on, not be
held there. On give-up the app plays the word once at normal speed and
continues.

Tracking which syllable was wrong on each attempt is nearly free and it is the
most interesting thing the app can say. If the user fixes syllable 2 and breaks
syllable 1, that is a real observation about overcorrection, and it is a good
line in a demo.
"""

from dataclasses import dataclass, field

MAX_ATTEMPTS = 4


@dataclass
class Session:
    entry: dict
    max_attempts: int = MAX_ATTEMPTS
    results: list = field(default_factory=list)

    @property
    def attempts(self) -> int:
        return len(self.results)

    @property
    def last(self) -> dict | None:
        return self.results[-1] if self.results else None

    def submit(self, result: dict) -> str:
        """Record a score() result. Returns "pass", "retry", or "give_up"."""
        self.results.append(result)

        if result["status"] == "no_speech":
            # Silence is not a failed attempt. Do not burn a retry on a mic
            # problem, and do not let it count toward giving up.
            self.results.pop()
            return "no_speech"

        if result["passed"]:
            return "pass"
        if self.attempts >= self.max_attempts:
            return "give_up"
        return "retry"

    def moved_on(self) -> bool:
        """True when the syllable being blamed changed between attempts.

        Usually means the user fixed the original problem and introduced a new
        one, which is worth saying out loud rather than repeating the same
        correction.
        """
        if len(self.results) < 2:
            return False
        return self.results[-1]["worst_syllable"] != self.results[-2]["worst_syllable"]

    def improving(self) -> bool:
        if len(self.results) < 2:
            return False
        prev, curr = self.results[-2], self.results[-1]
        return curr["worst_cost"] < prev["worst_cost"]

    def summary(self) -> dict:
        return {
            "word": self.entry["id"],
            "attempts": self.attempts,
            "passed": bool(self.last and self.last["passed"]),
            "scores": [r["score"] for r in self.results],
            "blamed": [r["worst_syllable"] for r in self.results],
        }
