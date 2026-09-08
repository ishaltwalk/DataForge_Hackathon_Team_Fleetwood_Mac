"""IPA -> Rime Phonetic Alphabet (RPA) conversion.

Input is the *already normalized* phone list your own pipeline produces
(core.phones.normalize -> core scripts.build_wordbank.syllabify), so every
symbol here is one of the 41 confirmed to actually occur in words.json.
Nothing is guessed from memory; the table below was built against that
exact inventory.

Two symbol classes:

  VOWELS       one IPA symbol -> one RPA vowel letter, stress digit prepended.
  DIPHTHONGS   two adjacent IPA symbols (kept as two segments by panphon's
               segmenter, same as everywhere else in this codebase) collapse
               into ONE RPA vowel + ONE stress digit, because they are one
               syllable nucleus, not two.
  CONSONANTS   direct 1:1, never take a stress digit.

Judgment calls, recorded rather than hidden:

  ɾ (flap, "subtle"/"daughter") -> 'd'. Perceptually closer to a fast /d/
    than /t/ in this position. Verify by ear if it matters for your demo;
    not re-derived from a rule, just a choice.
  ɔ / ɔː / oː / ɑː all fold onto RPA vowels Rime doesn't further subdivide
    (Rime has no separate LOT/CLOTH/THOUGHT/NORTH symbols): 'a' for the
    open-back set, and 'o' for oː specifically since it only ever occurs
    directly before ɹ in this data (the "or/door" quality), closer to the
    boat vowel's rounding than to 'a'. See words.json for real examples:
    according, transport, territory, recording.
  ɐ (unstressed word-initial "a-": another, american, available) -> 'x',
    treated as a reduced vowel like schwa since every occurrence here is
    unstressed.
"""

# (first_symbol, second_symbol) -> single RPA consonant. Same idea as
# DIPHTHONGS but for consonants: espeak/panphon segment the "ch" and "j"
# affricates as two adjacent phones (no tie bar survives normalize()), and
# unlike diphthongs these can straddle a syllable boundary -- "culture"
# syllabifies as ['k','ʌ','l','t'] + ['ʃ','ə','ɹ'], with the t and ʃ that
# together make one "ch" sound landing in different syllables. Missing this
# was the actual bug: mapping t and ʃ separately produces a hard T click
# followed by a separate SH, not one blended CH.
AFFRICATES = {
    ("t", "ʃ"): "C",
    ("d", "ʒ"): "J",
}

VOWELS = {
    "æ": "@", "ɑː": "a", "ʌ": "A", "ə": "x", "ɐ": "x", "ɛ": "E",
    "ɜː": "R", "ɪ": "I", "iː": "i", "i": "i", "ʊ": "U", "uː": "u",
    "ɔ": "a", "ɔː": "a", "oː": "o",
}

# (first_symbol, second_symbol) -> single RPA vowel. Checked before VOWELS,
# because 'a', 'e', 'o', and 'ɔ' are diphthong-only in this dataset (never
# occur as bare monophthongs) except 'ɔ' which is dual-use — see VOWELS.
DIPHTHONGS = {
    ("a", "ɪ"): "Y",
    ("a", "ʊ"): "W",
    ("e", "ɪ"): "e",
    ("ɔ", "ɪ"): "O",
    ("o", "ʊ"): "o",
}

CONSONANTS = {
    "b": "b", "d": "d", "f": "f", "h": "h", "k": "k", "l": "l",
    "m": "m", "n": "n", "p": "p", "s": "s", "t": "t", "v": "v",
    "w": "w", "z": "z", "ð": "D", "ŋ": "G", "ɹ": "r", "ɾ": "d",
    "ʃ": "S", "ʒ": "Z", "θ": "T", "ɡ": "g", "j": "y",
}

UNMAPPED: set[str] = set()   # anything neither table recognizes lands here


def word_to_rpa(ipa_syllables: list[list[str]], stresses: list[str]) -> list[str]:
    """words.json['ipa_syllables'] + one stress digit per syllable -> rpa_syllables.

    Processes the whole word as one flat phone sequence rather than syllable
    by syllable, because affricate pairs (see AFFRICATES) can span a syllable
    boundary and a per-syllable loop cannot see across it. Each produced RPA
    token is bucketed back into the syllable its FIRST consumed phone came
    from, so the return shape still matches ipa_syllables one-for-one.
    """
    assert len(ipa_syllables) == len(stresses), "syllable/stress count mismatch"

    flat = [(p, si) for si, syl in enumerate(ipa_syllables) for p in syl]
    out_by_syllable: list[list[str]] = [[] for _ in ipa_syllables]

    i = 0
    while i < len(flat):
        phone, syl_idx = flat[i]
        nxt = flat[i + 1][0] if i + 1 < len(flat) else None
        pair = (phone, nxt) if nxt is not None else None

        if pair in AFFRICATES:
            out_by_syllable[syl_idx].append(AFFRICATES[pair])
            i += 2
        elif pair in DIPHTHONGS:
            out_by_syllable[syl_idx].append(stresses[syl_idx] + DIPHTHONGS[pair])
            i += 2
        elif phone in VOWELS:
            out_by_syllable[syl_idx].append(stresses[syl_idx] + VOWELS[phone])
            i += 1
        elif phone in CONSONANTS:
            out_by_syllable[syl_idx].append(CONSONANTS[phone])
            i += 1
        else:
            UNMAPPED.add(phone)
            i += 1

    return ["".join(chunk) for chunk in out_by_syllable]
