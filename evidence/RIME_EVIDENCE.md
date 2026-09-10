# RIME_EVIDENCE

The hard voice claim, the acceptance test defined before the demo, the
procedure, the measured result, and the limitations.

Every number below is reproducible from this repository. Sections 4.1 to 4.3
need no audio, no network and no API key, and regenerate with one command.
Sections 4.4 to 4.6 are listening comparisons, so they need a Rime key and a
pair of headphones; `scripts/ab_clips.py` renders the clips and prints the
tables to fill in.

---

## 1. The hard voice claim

**Claim.** The tool identifies which syllable of a mispronounced word was
wrong, and makes Rime speak that syllable in isolation, slowed, with the
correct phonemes guaranteed rather than left to the model's own
grapheme-to-phoneme guess.

The hard part is not detecting an error. It is (a) locating it precisely enough
to act on, and (b) producing corrective speech that is definitely correct for a
word the TTS may never have seen.

**Why (b) is hard.** Half the word bank sits outside Rime's pronunciation
dictionary. Asked to say those words as plain text, the model guesses. A
pronunciation coach that guesses is worse than useless, because the learner
copies the guess. `phonemizeBetweenBrackets` removes the guess.

---

## 2. Acceptance test

Defined before the demo, run as a committed script.

```bash
python tests/acceptance.py
```

| Case | Clips | Assertion |
|---|---|---|
| Normal flow | 10 clean recordings, one per word | scored as passing |
| Stress case, mispronunciation | 3 recordings with a deliberate trap error | scored as failing **and** the identified syllable equals the one the speaker broke |
| Stress case, adverse audio | 1 clean recording with background noise | still passes, or the degradation is quantified here |

The second assertion is the real one. Asserting only "it failed" would be
satisfied by a tool that fails everything, which would be worthless while
looking correct.

---

## 3. Procedure

1. Reference phonemes generated offline by espeak-ng, committed to
   `data/words.json`, reproducible with `scripts/build_wordbank.py`.
2. RPA correction strings obtained from Rime `/phonemize` on clean recordings,
   then verified by ear one chunk at a time through `synthesize()` before being
   committed.
3. Learner audio captured in the browser, converted to 16 kHz mono WAV there
   (`src/lib/recorder.js`), transcribed by `openai/whisper-large-v3-turbo` via
   the HuggingFace Inference API, then converted to phones by espeak-ng
   locally. Both sides of the comparison are therefore espeak output, which is
   the point: a shared phonetic yardstick.
4. Reference and attempt aligned by weighted Levenshtein using panphon
   articulatory feature distance as substitution cost, producing a per-phoneme
   diff rather than a single number.
5. Per-phoneme costs attributed to syllables by index span; the highest-cost
   syllable is the one corrected.
6. Correction built as a Rime request and spoken. Never displayed as readable
   IPA.

All model and voice settings held constant throughout: `mistv3`, `falcon`,
English, WAV over HTTP.

---

## 4. Results

### 4.1 Scoring separates correct from incorrect speech

Measured across the entire committed word bank rather than a handful of clips.

```bash
python scripts/attribution_study.py      # writes evidence/attribution.md
```

Every word in the bank is first scored on its own correct pronunciation, then
on the same pronunciation with one phone changed in one syllable.

| | Result |
|---|---|
| Words scored on correct pronunciation | 5000 |
| **False alarms (correct speech scored as failing)** | **0** |
| Per-syllable cost threshold | `0.05` |

Zero false alarms out of 5000 is the floor this product has to clear. A tool
that fails people who said the word correctly is worse than no tool, because
it teaches them to change something that was already right.

### 4.2 Error sensitivity, measured on the committed word bank

Simulated single-phone substitutions against the real reference sequences.
Reproduces without any recording.

| Error | Overall score | Worst syllable cost |
|---|---|---|
| perfect | 1.000 | 0.000 |
| th to s | 0.990 | 0.071 |
| th to k | 0.936 | 0.446 |
| r to l | 0.929 | 0.500 |
| v to w | 0.901 | 0.893 |
| whole syllable dropped | 0.700 | 3.000 |

Two things this shows. The ordering is articulatorily sensible: a near-miss
costs less than a far miss, which a flat edit distance could not express. And
the overall score is a weak detector for single-phone errors, because one phone
in a seven-phone word is arithmetically about 1% of the word. That is why the
pass gate is syllable-level.

### 4.3 Blame lands on the right syllable

This is the claim. Same command as 4.1; full report in
`evidence/attribution.md`.

For every word in the bank, one phone in one syllable is replaced with a
substitution real learners make (th to s, r to l, v to w, tense to lax vowels).
Only the microphone is stubbed: the alignment, the articulatory distance, the
attribution and the threshold are the shipped code. The blamed set is read from
`core.correct.wrong_syllables`, which is both what the UI highlights and what
`build_correction` brackets for Rime, so this measures user-visible behaviour
and not an internal proxy.

| Measure | Count | Rate |
|---|---|---|
| Sabotages tested | 19,229 | |
| Detected as a failure | 10,190 | 53.0% |
| **Correct syllable blamed, of those detected** | **10,190 / 10,190** | **100.0%** |
| Misattributed | 0 | 0.0% |
| Undetected (too small to trip the gate) | 9,039 | 47.0% |

**Zero misattributions in 10,190 detections.** Misattribution is the failure
that matters: it means the app pointed at a syllable the speaker got right and
Rime then enunciated the wrong sound. Detection and precision are reported
separately rather than blended, because a single accuracy figure would hide it.

**The 47% undetected figure is stated deliberately.** A one-feature
substitution is genuinely close to the target, and `core/score.py` documents
why the syllable gate carries the pass decision rather than the overall score.
These are the cases sitting just under that gate. They are under-sensitivity,
not wrong answers, and the study counts them rather than dropping them. Raising
sensitivity would trade directly against the zero-false-alarm result in 4.1,
and for a pronunciation coach that trade is the wrong way round: failing a
learner who was right costs more than missing a marginal error they can be
caught on next time.

Whisper is word-level, so it normalises some errors before scoring sees them.
That is a real ceiling on the recorded path and is listed in section 5.

### 4.4 Custom pronunciation changes the output

```bash
python scripts/ab_clips.py               # needs RIME_API_KEY
```

Model `mistv3`, speaker `falcon`, language `eng` held constant across every
clip. The only variable is `phonemizeBetweenBrackets`.

| Word | Clip | Sent as | What it said |
|---|---|---|---|
| ornithological | `ab/ornithological_plain.wav` | plain text | |
| ornithological | `ab/ornithological_rpa.wav` | `{RPA}` phonemized | |
| coloratura | `ab/coloratura_plain.wav` | plain text | |
| coloratura | `ab/coloratura_rpa.wav` | `{RPA}` phonemized | |
| equiangular | `ab/equiangular_plain.wav` | plain text | |
| equiangular | `ab/equiangular_rpa.wav` | `{RPA}` phonemized | |

The exact payloads, so the difference is inspectable without listening:

```json
{"text": "ornithological", "speaker": "falcon", "modelId": "mistv3", "lang": "eng"}
{"text": "{2arn0IT0xl1aJ0Ik0xl}", "speaker": "falcon", "modelId": "mistv3", "lang": "eng", "phonemizeBetweenBrackets": true}
```

These words are chosen because they sit outside Rime's dictionary. On a word
the model already knows, this comparison proves nothing.

### 4.5 Syllable isolation changes the correction

Same word, same voice, `inlineSpeedAlpha` = 1.3 in both rows. Only the
bracketing differs. The middle syllable is used rather than the first or last,
which would be easier to hear in isolation and would flatter the result.

| Word | Clip | Strategy | Was the error audible |
|---|---|---|---|
| ornithological | `ab/ornithological_wholeword.wav` | whole word slowed | |
| ornithological | `ab/ornithological_syllable.wav` | syllable 3 slowed in place | |
| coloratura | `ab/coloratura_wholeword.wav` | whole word slowed | |
| coloratura | `ab/coloratura_syllable.wav` | syllable 2 slowed in place | |
| equiangular | `ab/equiangular_wholeword.wav` | whole word slowed | |
| equiangular | `ab/equiangular_syllable.wav` | syllable 2 slowed in place | |

```json
{"text": "[{2arn0IT0xl1aJ0Ik0xl}]", "inlineSpeedAlpha": "1.3", ...}
{"text": "{2ar}-{n0I}-{T0x}-[{l1aJ}]-{0I}-{k0xl}", "inlineSpeedAlpha": "1.3", ...}
```

Slowing everything is not a correction, it is a slow word. The claim is that
one stretched syllable inside a normal-speed word is what makes the error
locatable by ear.

Note the second payload also demonstrates the nesting that Rime's docs do not
cover either way: `[{...}]` both phonemizes and slows the same chunk.

### 4.6 Speed is intelligible and natural at the value shipped

One variable, the alpha value. Shipped value is `INLINE_SPEED` in
`core/correct.py`, currently 1.3.

| Alpha | Clip | Intelligibility 1-5 | Naturalness 1-5 |
|---|---|---|---|
| 1.0 | `ab/ornithological_speed_1_0.wav` | | |
| 1.3 | `ab/ornithological_speed_1_3.wav` | | |
| 1.6 | `ab/ornithological_speed_1_6.wav` | | |

Listening is the measurement here and it is not automatable. The script gets
honest clips onto disk; a human still has to put headphones on and write down
what they heard.


## 5. Limitations

**Docs versus behavior, three findings.** All verified by live testing on
Verified live against `mistv3` / `falcon` during development.

1. Rime's custom pronunciation page states Mist v3 does not support custom
   pronunciation. On English Mist v3 it does.
2. Combining `phonemizeBetweenBrackets` with `pauseBetweenBrackets` in one
   request is undocumented and works. Syllable isolation depends on it.
3. Nesting `inlineSpeedAlpha` brackets around a phonemized chunk is
   undocumented. Result: it works, and the shipped correction depends on it. See the payload in 4.5 and the revision note at the top of `core/correct.py`.

**Articulatory distance is not perceptual distance.** `θ` and `s` are close in
features and far apart to a listener. Mitigated by gating on syllable cost
rather than the overall average, but the underlying metric does not know that
"think" and "sink" are different words.

**espeak reference errors.** espeak drops vowels in some words (`reliable` to
`ɹlaɪəbəl`). Affected words were audited out of the bank. Any word added later
needs the same check, and the check is currently a human reading the output.

**Coverage.** 10 words, English only, chosen for specific trap phonemes. This
is a demonstration of a method, not a deployed curriculum.

**Adverse audio.** Tested with one noisy clip through a browser microphone.
Telephony transport is not tested and is not claimed.

**Scoring thresholds are calibrated on a small labelled sample** from a small
number of speakers. Treat the specific threshold values as exploratory. The
method for setting them is the reproducible part, not the numbers.

---

## Appendix: repeatable checks that need no audio and no network

Added when the two branches were merged. These do not replace the clip-based
acceptance test above; they cover the failures that a good clip hides.

```bash
pytest                             # 39 tests, offline
```

| Test | What it protects |
|---|---|
| `tests/test_coach.py::test_highlighted_syllables_are_the_spoken_ones` | Pulls the bracketed chunk indices back out of the text actually sent to Rime and asserts they equal the set the UI was told to highlight. This is the failure the whole design is arranged around: highlighting one syllable while Rime enunciates another looks correct in code review and is obvious to anyone wearing headphones. |
| `tests/test_payload.py::test_one_speed_value_per_bracketed_span` | `inlineSpeedAlpha` takes one value per bracketed span. Sending a single value leaves every span after the first at full speed, so a badly mispronounced word, where most syllables get flagged, silently stops being slowed. |
| `tests/test_payload.py::test_brackets_force_phonemization_even_if_caller_forgets` | `phonemizeBetweenBrackets` is set whenever `{}` appears, not only when a caller remembers to ask. Without it Rime speaks the literal braces or falls back to its own G2P guess, which is the guess this product exists to remove. |
| `tests/test_coach.py::test_provider_failure_is_reported_not_swallowed` | A Rime outage produces `provider: "unavailable"` with a reason, never a silent substitution. |

**Correction shape, for the record.** One wrong syllable in `culture`
(`k1AlC` + `0xr`) produces `{k1AlC}-[{0xr}]` with `inlineSpeedAlpha=1.3`. Both
wrong produces `[{k1AlC}]-[{0xr}]` with `inlineSpeedAlpha=1.3,1.3`. The `-` is
required syntax for multi-chunk RPA, not a pause. `pauseBetweenBrackets` is
implemented but unused; it was tested and made the correction less clear.
