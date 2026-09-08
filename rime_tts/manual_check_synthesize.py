import os
from rime_tts.synthesize import save, synthesize


def check_wav(path: str) -> bool:
    """Basic sanity check: file exists, isn't empty, and looks like a real WAV."""
    if not os.path.exists(path):
        print(f"  FAIL: {path} does not exist")
        return False

    size = os.path.getsize(path)
    if size < 1000:  # a few hundred bytes usually means an error response, not audio
        print(f"  FAIL: {path} is suspiciously small ({size} bytes) — likely an error, not audio")
        return False

    with open(path, "rb") as f:
        header = f.read(4)
    if header != b"RIFF":
        print(f"  FAIL: {path} does not start with RIFF — not a valid WAV file")
        return False

    print(f"  OK: {path} looks like valid audio ({size} bytes)")
    return True


def test_baseline():
    print("\n[Test 1] Baseline — plain text, no RPA")
    path = save(synthesize("Welcome to Rime labs.", speaker="falcon"), "test_baseline.wav")
    check_wav(path)


def test_rpa_whole_string():
    print("\n[Test 2] Whole-string RPA — known example from Rime docs")
    path = save(synthesize("Welcome to labs.", speaker="falcon", rpa="r1Ym"), "test_rpa.wav")
    check_wav(path)
    print("  Listen and confirm it says 'Rhyme', not literal '{r1Ym}'")


def test_rpa_mixed_sentence():
    print("\n[Test 3] RPA embedded mid-sentence (manual bracket insertion)")
    custom_text = "Welcome to {r1Ym} labs."
    path = save(synthesize(custom_text, speaker="falcon", rpa=None), "test_mixed.wav")
    # NOTE: this only works correctly if phonemizeBetweenBrackets gets set to True
    # even when rpa=None but {} appears manually in text — check your synthesize()
    # logic handles this case, or pass rpa="" as a workaround trigger if needed.
    check_wav(path)
    print("  Listen and confirm 'Rhyme' is pronounced correctly mid-sentence")


def test_edge_cases():
    print("\n[Test 4] Edge cases — numbers, names, punctuation")
    cases = {
        "test_numbers.wav": "Call me at 555-0142, or check unit 3B.",
        "test_name.wav": "My name is Xiomara.",
        "test_punct.wav": "Wait... did you say 'yes'?",
    }
    for filename, text in cases.items():
        path = save(synthesize(text, speaker="falcon"), filename)
        check_wav(path)


if __name__ == "__main__":
    test_baseline()
    test_rpa_whole_string()
    test_rpa_mixed_sentence()
    test_edge_cases()
    print("\nAll tests ran. Now go listen to each .wav file manually — file checks only prove it's audio, not that it sounds right.")