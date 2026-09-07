# Word bank build report

Derived from CMUdict (126052 entries), phonemized with espeak-ng, frequency from wordfreq Zipf. Regenerate with `python scripts/build_wordbank.py`.

**5000 words accepted** from 37961 candidates.

## Composition

| tier | count |
|---|---|
| common | 1000 |
| mid | 2250 |
| showcase | 1750 |

| syllables | count |
|---|---|
| 2 | 302 |
| 3 | 1143 |
| 4 | 1770 |
| 5 | 1371 |
| 6 | 353 |
| 7 | 51 |
| 8 | 8 |
| 9 | 1 |
| 12 | 1 |

Mean difficulty score 5.8 (threshold 3).

| difficulty feature | count |
|---|---|
| late stress | 2606 |
| trap phoneme | 2103 |
| 2 trap phoneme(s) | 1848 |
| long, high syllable load | 1785 |
| four syllables | 1770 |
| 3-consonant cluster | 1527 |
| repeated sounds invite metathesis | 1135 |
| 3 trap phoneme(s) | 471 |
| 4-consonant cluster | 208 |
| spelling misleads | 117 |
| 4 trap phoneme(s) | 32 |
| 5-consonant cluster | 1 |

## Rejections

Automatic, not editorial.

| reason | count |
|---|---|
| not hard enough to be worth practising | 17265 |
| single syllable, nothing to isolate | 5894 |
| AUDIT 2: phones disagree with CMUdict | 1523 |
| AUDIT 1: syllable count disagrees with CMUdict | 1211 |

### Audit 1, dropped vowels

espeak's syllable count disagrees with the dictionary, meaning it dropped a vowel. A learner saying these correctly would be marked wrong against the reference.

* `aba -> ɐbæ (2 vs 3)`
* `abalone -> ɐbæloʊn (3 vs 4)`
* `abasia -> ɐbeɪsiə (4 vs 3)`
* `abler -> eɪbləɹ (2 vs 3)`
* `abyssinia -> ɐbɪsɪniə (5 vs 4)`
* `abyssinian -> ɐbɪsɪniən (5 vs 4)`
* `academe -> ɐkædəmi (4 vs 3)`
* `acampsia -> ɐkæmpsiə (4 vs 3)`
* `accompaniment -> ɐkʌmpɐnɪmənt (5 vs 4)`
* `accursed -> ɐkɜːsɪd (3 vs 2)`
* `actuarial -> æktʃuːɛɹɪəl (4 vs 5)`
* `ade -> ɐdɛ (2 vs 1)`
* `adios -> ædjoʊs (2 vs 3)`
* `adlai -> ædlaɪ (2 vs 3)`
* `admire -> ɐdmaɪəɹ (3 vs 2)`
* `admirer -> ɐdmaɪəɹəɹ (4 vs 3)`
* `admiring -> ɐdmaɪəɹɪŋ (4 vs 3)`
* `admiringly -> ɐdmaɪəɹɪŋli (5 vs 4)`
* `adverbial -> ædvɜːbɪəl (3 vs 4)`
* `aeneid -> iːneɪd (2 vs 3)`
* `aerial -> ɛɹɪəl (2 vs 3)`
* `afire -> ɐfaɪəɹ (3 vs 2)`
* `afl -> æfəl (2 vs 3)`
* `agamemnon -> æɡeɪmmnən (3 vs 4)`
* `aguacate -> æɡjuːækeɪt (4 vs 3)`
* `ahluwalia -> ɑːluːweɪliə (5 vs 4)`
* `aka -> ækɐ (2 vs 3)`
* `alameda -> ɐleɪmdə (3 vs 4)`
* `albion -> ælbɪən (2 vs 3)`
* `aleatory -> ɐliːtoːɹi (4 vs 5)`

### Audit 2, wrong phones

The syllable count is right but the sounds are not. Mostly loanwords, where espeak applies English spelling rules to a word that does not follow them, and rare clusters where it gives up.

* `abele -> eɪbəl (disagreement 0.60)`
* `ablest -> eɪbləst (disagreement 0.29)`
* `abram -> eɪbɹæm (disagreement 0.33)`
* `accurate -> ækjʊɹət (disagreement 0.29)`
* `acerbic -> ɐsɜːbɪk (disagreement 0.29)`
* `acetic -> ɐsiːɾɪk (disagreement 0.33)`
* `acetylcholine -> æsɪtɪlkəliːn (disagreement 0.33)`
* `achill -> ɐtʃɪl (disagreement 0.40)`
* `achor -> ɐtʃoːɹ (disagreement 1.00)`
* `acidity -> æsɪdɪɾi (disagreement 0.29)`
* `acuity -> ɐkjuːɪɾi (disagreement 0.29)`
* `adolph -> ædɑːlf (disagreement 0.50)`
* `adrenergic -> ɐdɹənɜːdʒɪk (disagreement 0.27)`
* `adriatic -> ædɹɪæɾɪk (disagreement 0.33)`
* `ady -> ɐdaɪ (disagreement 0.75)`
* `aeolus -> iːɑːləs (disagreement 0.67)`
* `aerobatic -> ɛɹoʊbæɾɪk (disagreement 0.33)`
* `aerobatics -> ɛɹoʊbæɾɪks (disagreement 0.30)`
* `aeronautic -> ɛɹoʊnɔːɾɪk (disagreement 0.33)`
* `aeronautical -> ɛɹoʊnɔːɾɪkəl (disagreement 0.27)`
* `aeronautics -> ɛɹoʊnɔːɾɪks (disagreement 0.30)`
* `affinity -> ɐfɪnɪɾi (disagreement 0.29)`
* `affricate -> ɐfɹɪkeɪt (disagreement 0.38)`
* `afrikaner -> æfɹɪkeɪnəɹ (disagreement 0.33)`
* `afshar -> ɐfʃɑːɹ (disagreement 0.40)`
* `agar -> eɪɡɑːɹ (disagreement 0.40)`
* `agate -> æɡeɪt (disagreement 0.40)`
* `agee -> ædʒiː (disagreement 0.40)`
* `ageratum -> eɪdʒəɹɑːɾəm (disagreement 0.56)`
* `aggregate -> æɡɹɪɡeɪt (disagreement 0.38)`