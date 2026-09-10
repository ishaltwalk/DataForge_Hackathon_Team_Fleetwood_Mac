INLINE_SPEED = "1.3"


def wrong_syllables(syllable_costs: list[float], threshold: float) -> set[int]:
    flagged = {i for i, cost in enumerate(syllable_costs) if cost > threshold}
    if flagged:
        return flagged
    if not any(cost > 0 for cost in syllable_costs):
        return set()
    return {max(range(len(syllable_costs)), key=lambda i: syllable_costs[i])}


def build_correction(entry: dict, wrong_indices: set[int]) -> dict:
    chunks = entry["rpa_syllables"]
    assert chunks, f"{entry['id']} has no RPA syllables"

    parts = []
    for i, syl in enumerate(chunks):
        chunk = "{" + syl + "}"
        if i in wrong_indices:
            chunk = "[" + chunk + "]"
        parts.append(chunk)

    n_bracketed = len(wrong_indices & set(range(len(chunks))))
    speed = ",".join([INLINE_SPEED] * n_bracketed) if n_bracketed else None

    return {
        "text": "-".join(parts),
        "phonemize_brackets": True,
        "pause_brackets": False,
        "inline_speed": speed,
    }


def build_prompt(entry: dict) -> dict:
    return {
        "text": "{" + "".join(entry["rpa_syllables"]) + "}",
        "phonemize_brackets": True,
        "pause_brackets": False,
    }


def coaching_line(entry: dict, wrong_indices: set[int]) -> str:
    if not wrong_indices:
        return "I did not hear anything that time."
    ordinal = ["first", "second", "third", "fourth", "fifth", "sixth"]
    names = [ordinal[i] if i < len(ordinal) else "last" for i in sorted(wrong_indices)]
    if len(names) == 1:
        return f"The {names[0]} syllable is the one to fix."
    return f"The {', '.join(names[:-1])} and {names[-1]} syllables need work."
