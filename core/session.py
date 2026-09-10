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
        self.results.append(result)

        if result["status"] == "no_speech":
            self.results.pop()
            return "no_speech"

        if result["passed"]:
            return "pass"
        if self.attempts >= self.max_attempts:
            return "give_up"
        return "retry"

    def moved_on(self) -> bool:
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
