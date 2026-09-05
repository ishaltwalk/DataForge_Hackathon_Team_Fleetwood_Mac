import os
from synthesize import synthesize
from phonemize import phonemize


def check_wav(path: str) -> bool:
    """Basic sanity check: file exists, isn't empty, and looks like a real WAV."""
    if not os.path.exists(path):
        print(f"  FAIL: {path} does not exist")
        return False

    size = os.path.getsize(path)
    if size < 1000:
        print(f"  FAIL: {path} is suspiciously small ({size} bytes) — likely an error, not audio")
        return False

    with open(path, "rb") as f:
        header = f.read(4)
    if header != b"RIFF":
        print(f"  FAIL: {path} does not start with RIFF — not a valid WAV file")
        return False

    print(f"  OK: {path} looks like valid audio ({size} bytes)")
    return True


def check_phoneme_string(rpa: str) -> bool:
    """Basic sanity check on the returned phoneme string."""
    if not rpa or not isinstance(rpa, str):
        print(f"  FAIL: phonemeString is empty or not a string: {rpa!r}")
        return False

    if rpa.strip() != rpa:
        print(f"  WARN: phonemeString has leading/trailing whitespace: {rpa!r}")

    print(f"  OK: got phoneme string: {rpa!r}")
    return True


def test_phonemize_basic():
    print("\n[Test 1] Phonemize a known reference word")
    # First synthesize a clean reference clip to phonemize back
    ref_path = synthesize("Rhyme", speaker="falcon", output_path="ref_rhyme.wav")
    check_wav(ref_path)

    rpa = phonemize(ref_path)
    check_phoneme_string(rpa)
    return rpa


def test_round_trip(rpa: str):
    print("\n[Test 2] Round-trip — feed phonemize() output back into synthesize()")
    if not rpa:
        print("  SKIP: no phoneme string from Test 1")
        return

    path = synthesize("", speaker="falcon", rpa=rpa, output_path="round_trip.wav")
    check_wav(path)
    print(f"  Listen to {path} and confirm it still says the intended word correctly")


def test_mismatched_content_type():
    print("\n[Test 3] Sanity check — wrong Content-Type on a real WAV file")
    print("  (Manual check: temporarily change headers Content-Type to 'audio/mpeg'")
    print("   in phonemize.py and confirm it errors or behaves unexpectedly.")
    print("   Revert after checking — this isn't automated since it requires editing the function.)")


if __name__ == "__main__":
    rpa = test_phonemize_basic()
    test_round_trip(rpa)
    test_mismatched_content_type()
    print("\nAll tests ran. Listen to ref_rhyme.wav and round_trip.wav manually to confirm they sound the same word.")