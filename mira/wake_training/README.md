# Mira wake word training («ميرا» / «يا ميرا» / «هاي ميرا»)

Tools that train Mira's Arabic wake word for the owner's Echo Dot 2 (TECHO5 Dot Linux). echod
runs openWakeWord models: its own Go front end turns 16 kHz audio into one 96-value speech
embedding per 80 ms step, and a small TFLite classifier scores the last 16 embeddings. Everything
here computes features with that same Go code, so training sees exactly what the device computes.

Since 2026-09-29 the owner wants the Echo to wake **only** for Mira, with Alexa removed, so the Mira
model carries the load alone. `mira_ar_v2` is the synthetic model for that. `train_owner.py`
retrains it on the owner's own voice once the app has recorded him.

Nothing here connects to the Echo. Owner audio is read where it is. Derived features and models
stay in the training directory and are never committed.

| File | What it is |
| --- | --- |
| `train_owner.py` | trains the model (with or without owner captures); writes model, manifest and report |
| `mira_ar_v2.tflite`, `mira_ar_v2.json` | the synthetic-diverse model, ready to install (below); `mira_ar_v2-report.{md,json}` |
| `synth_corpus.py` | the cached synthetic corpus: Piper positives, Gemini voices, confusables, words, sentences |
| `gemini_tts.py` | optional: natural voices from Gemini TTS (free tier, key read from the app's config, never printed) |
| `selftest_owner.py` | builds a synthetic STAND-IN owner and runs `train_owner.py` on it |
| `wakelib.py` | shared code: Go front end runner, timing, augmentation, segmentation, trainer, TFLite I/O, device-logic metrics |
| `mira_features_test.go` | exports echod's embeddings (and scores through echod's engine); dropped into a copy of TECHO5's `oww` package |
| `repro_synthetic.py` | rebuilds the committed synthetic-only model with the untouched `generate.py` + `train.py` and compares |
| `setup.sh`, `fetch_data.py` | install Go, the TECHO5 package copy, the venv, voices, background features and the corpus |
| `generate.py`, `train.py` | the first pipeline, unchanged (it produced `mira_ar_experimental.tflite`) |
| `mira_ar_experimental.tflite`, `training-report.json` | the first synthetic-only model and its report |

## Setup

On the host (from the VS Code Flatpak sandbox: prefix `flatpak-spawn --host`). No root needed.

```sh
cd mira/wake_training
sh setup.sh --prefix ~/.local/share/mira/wake-train      # where the desktop app looks (wake_coach.py)
sh setup.sh --prefix ~/.local/share/mira/wake-train --seed-from ~/.cache/mira-claude/wake   # reuse a built cache
```

Without `--prefix` the directory is `$MIRA_WAKE_CACHE`, else `$MIRA_WAKE_TRAIN_ENV`, else
`~/.cache/mira-claude/wake`. The scripts find it the same way, and the app sets
`MIRA_WAKE_TRAIN_ENV`. `setup.sh` is idempotent and checksum-pinned. It installs:

- `go/`: go1.26.8 linux-amd64 (official tarball, sha256 `d0f743b3…`). echod's module says `go 1.26.0`.
- `techo5-echod/`: a copy of `echod/go.mod`, `go.sum` and `internal/lib/{oww,tflite,vec}` from
  `TECHO5_SRC` (default `/var/home/moos/moos-image/test-results/echo-dot/techo5`), plus
  `mira_features_test.go`. Pure Go: no cgo, no TFLite C library. Builds offline (`GOPROXY=off`).
- `venv/`: host Python 3.14 with numpy 2.5.3, scipy 1.18.1, scikit-learn 1.9.1, piper-tts 1.8.0,
  flatbuffers 25.12.19, tflite 2.18.0, onnxruntime 1.30.0, faster-whisper 1.2.1.
- `voices/`: Piper `ar_JO-kareem-medium`, `en_US-libritts_r-medium`, `en_US-l2arctic-medium` (+ model cards).
- `data/validation_set_features.npy` (185 MB) and `data/acav100m_sample_300x500.npy` (461 MB,
  a fixed sample fetched with HTTP range requests; see Licensing).
- `synth/`: the corpus, in parts cached by the hash of their spec. Positives take ~50 min
  (each is checked with the Whisper model Mira already has at `~/.local/share/mira/wake-model`),
  negatives ~3 min, the Gemini part ~20 min.
- `gemini/`: cached Gemini TTS calls (only if `gemini_tts.py` was run); `featcache/`: front-end
  outputs keyed by audio content (safe to delete).

Run long jobs as capped user services, so a mistake cannot take the desktop down:
`systemd-run --user --collect -p MemoryMax=7G -E OPENBLAS_NUM_THREADS=8 ...`. A corpus bug of mine
reached 10 GB and was OOM-killed on 2026-09-29 (it also stopped the sandbox's host-command helper).

## What was measured about the device front end

- TECHO5's embedded `melspectrogram.tflite` and `embedding_model.tflite` are byte-identical to
  openWakeWord v0.5.1's (sha256 `96fa0adc…`, `c0aea21e…`).
- On real (noisy) audio the Go front end equals openWakeWord's ONNX reference: max |Δ| 8e-5, mean
  1e-5, for embeddings whose standard deviation is 16, with the same embedding alignment. So the
  openWakeWord feature sets are valid negatives for this device.
- The mel model floors its output 80 dB below the loudest value of each 1760-sample chunk
  (`ReduceMax → Sub → Clip` in the graph). On digital silence the features therefore depend on
  the chunking, and the exporter's one second of zero padding makes windows the device never
  sees. In `train.py` about half of every positive window was that padding. The new pipeline
  exports with `MIRA_PAD=0` and gives every clip real room sound before and after the word.
- Timing (impulses on a noise bed): embedding `i` of a stream depends on samples
  `[1280·i + 56, 1280·i + 12456)` (mel frames 8i … 8i+75), and window `w` (embeddings w … w+15)
  ends at sample `1280·(w+15) + 12456`. echod scores every window, once per 80 ms step.
- Speed: 3.6 ms per 80 ms step per core (22× real time). The parallel batch exporter produced
  byte-identical `.features` for all 400 clips of the first corpus in 8.8 s (the original loop: 59 s).
- Scores from echod's engine (`TestMiraScore`: `Engine.Load` + `Process`) equal the numpy scoring
  of the same embeddings within 1e-6, for the 32-unit and the 96-unit models.
- Detection logic (`feature/detect/engine.go`): a score ≥ cutoff fires at once. Scoring then holds
  300 ms for the peak, followed by 800 ms refractory, so detections are at least 14 steps (1.12 s)
  apart. A peak ≥ 0.5 that never fired is logged as a near miss. While the echo canceller runs
  (music playing) the cutoff drops by 0.10, never below 0.50. The cutoff belongs to the SLOT: the
  "Wake word sensitivity" number `wake_threshold_<slot>` (0.50–0.99; echod's default 0.85). With
  Mira alone it is slot 1, `wake_threshold_1`.

## Why bare «ميرا» scored low with the first model

- Piper runs an Arabic diacritizer before espeak. It reads «مِيرا» as `mˈiːran` (tanween),
  «يا مِيرا» as `jˈaː mˈiːran` and «ميرا ميرا» as `mˈiːran mˈiːran`. Only «هاي مِيرا» and «مِيرَا»
  come out as `…mˈiːraː`. So three of the five positive phrases of `generate.py` (60 % of the
  positives, and every «يا ميرا») said "-an".
- Every positive window was half digital silence (above). The model learned "silence, then the word",
  which is conservative on real audio.
- There was one speaker.
- Together these fit the measurement: «هاي ميرا» scored 0.82–0.91 on the device while bare «ميرا»
  often stayed below 0.5.

## Voices

| Source | Used for | Evidence |
| --- | --- | --- |
| Piper `ar_JO-kareem-medium`, IPA (`mˈiːraː`, `miːrˈaː`, `jˈaː mˈiːraː`, `hˈaːj mˈiːraː` …) | positives, confusables, words, sentences | Whisper heard "Mira" in 720 of 817 (kept only those) |
| Gemini TTS, 26 prebuilt voices × 10 styles/accents, «ميرا» «ميرا؟» «ميرا!» «يا ميرا» «هاي ميرا» | positives (20 voices train, 6 held out), a few negatives | free tier: 10 requests/day/model (quota id `GenerateRequestsPerDayPerProjectPerModel-FreeTier`); on 2026-09-29, 31 answered requests (10–11 per model: `gemini-2.5-flash-preview-tts`, `gemini-3.1-flash-tts-preview`, `gemini-3.8-flash-tts`), 2 without audio, 3 quota refusals; 30 of 42 planned jobs cached; 194 positives kept after the Whisper check |
| Piper `en_US-libritts_r-medium` (904 speakers), `en_US-l2arctic-medium` (24) | negatives (English words, confusables, sentences) | as positives ("Meera") they taught a broad "mi-rV" that fired ~200/h on English conversation, so they no longer train positives |
| tape shift (resample + WSOLA, pitch and formants ×0.84–1.16) of 60 % of the synthetic positives | speaker size | Whisper still hears "Mira" (6/6 at ×0.92); an LPC pitch/formant shift made "Mew", "Leo" (3/18) and was dropped |
| espeak-ng Arabic (voices m3, m7, f2, f4, klatt2; pitch and rate varied) | not used | Whisper heard "Mira" in 6 of 48 ("Liqai", "Be right", "Yummy") |
| Piper `ar_JO-kareem-low` | not used | heard as "Lira" 7 of 8 |

Some Gemini calls read the style instruction aloud; segmentation plus the Whisper check drop those
segments from the positives (120 rejected). The remaining 12 planned calls (8 negative lists, 4 more
voices) can run on a later day: `python gemini_tts.py --holdout-first`.

## What brought false accepts down

Measured on the 10.7 h background set (below); single models except the last row:

| Change | False accepts/h at 0.5 / 0.6 / 0.7 |
| --- | --- |
| realistic context, 50 % of the weight on positives, English + Arabic positives | 305 / 230 / 169 |
| Arabic positives only, 35 % on positives | 110 / 84 / 63 |
| real conversation as the only background negatives (even 10-min blocks of the validation set) | 61 / 40 / 22 (on the held-out odd blocks) |
| 10 % on positives + 2 rounds of hard-negative mining (top 1 % of negatives ×4) | 10.7 / 4.9 / 2.4 |
| 3 % on positives | 0.4 / 0.2 / 0 — but recall collapses (unseen voices 0.39 at 0.6) |
| 4 mining rounds | 1.1 / 0.4 / 0.1 — recall falls to 0.57 |
| final `mira_ar_v2` (Piper + Gemini positives by clip count, 10 %, 2 rounds, L2 0.01, 3 seeds) | 9.7 / 5.1 / 2.5 |

Also: a 64-unit hidden layer was no better than 32. Weighting each voice family equally lifted
Gemini recall but lowered everything else. The hidden layer's dead units decayed into subnormal
floats and made later epochs 20× slower; the trainer now flushes |w| < 1e-30 to zero. Single
seeds of one configuration differed by up to 12 points of stand-in recall at the same cutoff, so the
model is an ensemble: averaging K models'
logits is itself one MLP (hidden layers side by side, output layer / K), exported with the same
three operators (`--ensemble 3`: FC(96, RELU) → FC → LOGISTIC, 591 KB).

## 1. Reproducing the committed model

```sh
~/.cache/mira-claude/wake/venv/bin/python repro_synthetic.py      # --fresh to regenerate
```

It runs the untouched `generate.py` (Piper corpus) → the Go exporter (`MIRA_CLIPS` mode) →
`train.py` in `<cache>/repro/`, then scores both models on the same data. Piper samples noise
inside the model, so the corpus and the weights differ from the committed run; the behaviour
matches. Measured 2026-09-29 (`<cache>/repro/repro-report.json`):

| | committed | rebuilt |
| --- | --- | --- |
| `train.py`'s own metrics: holdout recall / negative false rate (windows, ≥ 0.5) | 1.000 / 0.013 | 0.975 / 0.006 |
| background false windows at stride 16 (last 20 %), peak | 1 of 6016, 0.667 | 1 of 6016, 0.519 |
| synthetic holdout positive clips detected at 0.5 / 0.6 / 0.7 | 100 % / 100 % / 100 % | 100 % / 100 % / 100 % |
| synthetic holdout negative clips firing at 0.5 / 0.6 / 0.7 | 17.5 % / 15 % / 15 % | 10 % / 5 % / 5 % |
| device-logic false accepts per hour, last 20 % of the validation set (2.14 h), at 0.5 / 0.6 / 0.7 | 3.74 / 2.81 / 0.94 | 0.94 / 0.94 / 0.47 |
| score correlation on the holdout windows | 0.97 | |

## 2. `mira_ar_v2` (synthetic voices, no owner audio)

```sh
PY=~/.local/share/mira/wake-train/venv/bin/python
$PY train_owner.py --out OUT --id mira_ar_v2 [--eval-captures DIR]
```

`mira_ar_v2.tflite` here: sha256 `ab904005…`, 591,456 bytes, 1×16×96 → FC(96, RELU) → FC →
LOGISTIC, float32; `mira_ar_v2.json` = `{"wake_word": "ميرا", "model": "mira_ar_v2.tflite",
"trained_languages": ["ar"]}`. Trained in 5.5 min. Held-out data only, against the committed model
(`mira_ar_v2-report.md` has everything):

| cutoff | background FA/h, 10.7 h (95 % CI) | FA/h last 2.1 h: v2 / committed | unseen Gemini voices: v2 / committed | Kareem clips | stand-in speaker | Arabic + English confusables fired |
| --- | --- | --- | --- | --- | --- | --- |
| 0.50 | 9.7 | 7.9 / 3.7 | 0.89 / 0.78 | 0.89 / 0.81 | 0.84 / 0.86 | 3.6 % / 17.9 % |
| 0.60 | 5.1 (3.9–6.7) | 5.1 / 2.8 | 0.89 / 0.76 | 0.86 / 0.78 | 0.76 / 0.82 | 1.9 % / 15.5 % |
| **0.65** | **3.6 (2.5–4.9)** | 2.8 / 2.3 | — | — | 0.75 / 0.80 | 1.4 % / 13.8 % |
| 0.70 | 2.5 (1.7–3.7) | 2.8 / 0.9 | 0.83 / 0.70 | 0.79 / 0.74 | 0.68 / 0.76 | 1.0 % / 13.1 % |
| 0.80 | 0.8 | 0.9 / 0.5 | | | 0.54 / 0.71 | 0.5 % / 9.8 % |

At equal false-accept budgets (fine 0.01 grid): at ≤ 1/h, unseen Gemini voices 0.80 vs 0.65 and
confusables 0.5 % vs 8.8 %; at ≤ 2/h, 0.80 vs 0.67 and 1 % vs 12.6 %. The committed model is ahead only
on the stand-in, which is built from Kareem, its single training voice (0.54 vs 0.71 at ≤ 1/h).
The committed model's full-set figures are optimistic: it trained on 80 % of that audio.

**Recommended cutoff 0.65** (`wake_threshold_1` with Mira alone). It is the lowest cutoff whose
false accepts (3.6/h) are at or below the committed model's at today's working cutoff 0.60 (4.96/h
on the same audio). That is "no more false wakes than today", with about a tenth of the confusable
wakes. While music plays echod uses 0.55. This is a synthetic-voice estimate. The owner's own
«ميرا» can score lower or higher, so watch echod's near-miss lines (`wake near miss … peak`) and
retrain with his captures.

## 3. Training on the owner's voice

The desktop app records 16 kHz mono WAV windows into `~/.local/share/mira/wake-enrol/mira/*.wav`
(and non-wake speech into `…/other/*.wav`) and runs, from `wake_coach.py`:

```sh
~/.local/share/mira/wake-train/venv/bin/python wake_training/train_owner.py \
    --owner ~/.local/share/mira/wake-enrol/mira --out WORKDIR --id MODEL_ID \
    [--negatives ~/.local/share/mira/wake-enrol/other]      # env MIRA_WAKE_TRAIN_ENV=~/.local/share/mira/wake-train
```

### Contract

- Input: `--owner DIR` (or positional): **16 kHz, mono, 16-bit signed little-endian PCM WAV**, one Echo
  listening window per file (up to ~15 s) as the voice pipeline streams it, several «ميرا» /
  «يا ميرا» / «هاي ميرا» separated by pauses of about a second or more. Anything else is refused
  with the reason (exit status 1). At least two files must contain utterances (one is held out).
  `NAME.json` beside `NAME.wav` with `{"utterances": [[start_s, end_s], ...]}` replaces the automatic
  segmentation for that file.
- `--negatives DIR`: owner clips WITHOUT the wake word (same format, any length). Every fourth file is
  held out when there are four or more.
- `--id ID` (`[a-z0-9_]{3,40}`, default `mira_ar_owner`); `--out DIR`; `--expect N` (warn when a
  capture has another count); `--strict` (leave such captures out); `--eval-captures DIR` (evaluate on
  captures that never train); `--refit-all` (after evaluating, retrain on every capture and export that
  model; `<id>.evaluated.tflite` keeps the evaluated one). Other knobs keep their measured defaults
  (`--ensemble 3 --pos-share 0.1 --mine-rounds 2 --l2 0.01 --pos-window 0.08,0.40 --aug 40`).
- Output in `--out`: `<id>.tflite`, `<id>.json` (`{"wake_word": "ميرا", "model": "<id>.tflite",
  "trained_languages": ["ar"]}`, `--phrase` sets wake_word), `report.json`, `report.md`, `train.log`.
- `report.json` top level (stable; what `wake_coach.summarize` reads): `recommended_cutoff` (number on the
  0.05 grid, e.g. `0.65`), `owner_holdout` (`total`, `hits` at the recommended cutoff,
  `by_cutoff["0.5"…"0.95"]` → `hits`, `total`, `recall`; `null` without owner captures),
  `false_accepts_per_hour_estimate` (background, at the recommended cutoff), `path`. Details:
  `owner.captures` (per file: split, utterance count, warnings, segments), `holdout` (per-utterance peaks
  for the new and the committed model, recall per cutoff with 95 % intervals, false detections outside
  utterances), `owner_negatives_detections`, `eval_captures`, `synthetic_holdout`, `background`,
  `cutoff_recommendation` (value, reason, table, the cutoff while music plays), `engine_check`,
  `training`, `timings_s`.
- Runtime on this PC (i5-14400F, 16 threads, shared with the desktop): 8.4 min for 12 captures + 4
  negative files the first time (augmentation 1.3 min, front end 3.5 min, three ensemble members 3.4
  min); about 5 min when the synthetic features are already cached. The app's timeout is 30 min.
- Checked 2026-09-29 exactly as `wake_coach.py` runs it, in `~/.local/share/mira/wake-train` with
  `MIRA_WAKE_TRAIN_ENV` set, on the stand-in set below: exit 0 in 486 s. `wake_coach.summarize` of that
  report: `{'cutoff': 0.8, 'holdout_hits': 16, 'holdout_total': 22, 'false_per_hour': 0.561}`; of
  `mira_ar_v2`'s: `{'cutoff': 0.65, 'holdout_hits': None, 'holdout_total': None, 'false_per_hour': 3.553}`.

### What it does

1. Segments each capture: speech band 120–4000 Hz, 20 ms frames, thresholds relative to the capture's
   own noise floor (15th percentile) and speech level (99th) with hysteresis. Pauses under 0.25 s
   merge. Over-long regions and regions touching the edges split at energy valleys. Set aside:
   - `cut_off`: touches the start or end. The Echo only streams after the loud part of its wake
     sound, so a sound already running at 0 s is its tail or clipped speech.
   - `faint`: more than 15 dB below the loudest speech (television, another room).
   - `too_short` (< 0.15 s) and `too_long` (> 1.8 s).
2. Holds out whole files until ~25 % of the utterances are held out.
3. Builds training clips, every one with real sound around the word:
   - each owner utterance ×40: speed ×0.92–1.08, level ±12 dB (peak under −1 dBFS like the
     leveller), a synthetic room (p 0.4), extra noise at 5–20 dB SNR (p 0.75) from the owner's own
     background, babble, pink/brown/white/fan noise or hum, all over his room sound;
   - the training captures as recorded;
   - the synthetic corpus (Piper and Gemini positives, 60 % tape-shifted; confusables, words,
     sentences);
   - his negatives;
   - 150,000 ACAV100M windows.
4. Computes every embedding with echod's Go front end.
5. Trains three seeds (weighted cross-entropy, 10 % of the weight on positives, Adam, L2, early
   stopping, 2 hard-negative rounds) and merges them into one model.
6. Evaluates on the owner holdout, synthetic holdout and background. It also checks echod's engine
   against the Python scoring.

### Choosing the cutoff

On the 0.05 grid, 0.50–0.95:

- With owner captures, `c_min` is the lowest cutoff with ≤ 1 background false accept per hour
  (`--fa-target`). If a held-out utterance is already missed there, the recommendation is `c_min`.
  Otherwise it is 0.10 below the weakest held-out utterance's peak, not below `c_min` and not
  above 0.90.
- Without owner captures, it is the lowest cutoff with no more false accepts than the committed
  model at its working 0.60 (`--baseline-cutoff`).

The report also gives the cutoff echod uses while music plays.

### How the false-accept rate is estimated

The background set is openWakeWord's validation features: 10.70 h of continuous audio (DiPCo
dinner-party conversation 5.3 h, Santa Barbara conversational English 3.7 h, MUSDB music played
through measured room responses 2 h). Every stride-1 window is scored, one score per 80 ms step as
on the device, and echod's detection logic is applied (fire at ≥ cutoff, then 14 steps deaf). The
detections are divided by 10.70 h, with an exact 95 % Poisson interval. Nothing in it is Arabic and
nothing is the owner's home, so it is a lower bound for an Arabic-speaking household. Read it with
the confusable-word rates and the held-out owner negatives. The committed model was trained on the
first 80 % of this set, so its full-set figures are optimistic and the last 20 % (2.14 h) is the
fair comparison.

## 4. Self-test with a stand-in owner

No owner audio exists yet, so `selftest_owner.py` makes a **STAND-IN** that is not the owner:

- Piper Kareem (IPA) made into a larger speaker by tape shift ×0.85, 7 % slower, with variation per
  utterance.
- 12 captures of 15 s, each with six «ميرا» / «يا ميرا» / «هاي ميرا» (60 % bare) and 1–2 s pauses.
- Near and far rooms (RT60 0.45 / 0.7 s); quiet, television babble 16–24 dB down, or hum/fan.
- Echo band limits and leveller.
- The real wake-sound tail at the start of half of them.
- 4 more captures of the same "speaker" saying confusables and sentences, as `--negatives`.

It runs `train_owner.py … --expect 6` on the set, and again with `--synthetic-only`:

```sh
~/.cache/mira-claude/wake/venv/bin/python selftest_owner.py     # --summary-only to re-read finished runs
```

Segmentation against the known times: all 72 utterances found, 4 extra segments (television fragments,
all in the one television capture, which `--expect 6` flagged), median error 0.05 s at the start and
0.24 s at the end (p90 0.33 s; energy ends include the room's decay). The split put 3 captures (22
segments, 18 true utterances; one of them the television + wake sound capture) in the holdout.

| Held out (18 true utterances) | recall 0.5 | 0.6 | 0.7 | 0.8 | 0.9 | background FA/h at 0.5 / 0.6 / 0.7 / 0.8 | held-out owner-negative capture: detections at 0.5 / 0.7 / 0.8 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `train_owner.py` (stand-in audio + synthetic) | **0.89** | **0.89** | **0.89** | **0.89** | 0.78 | 6.9 / 3.2 / 1.7 / 0.56 | 1 / 1 / 1 |
| same recipe, `--synthetic-only` (= the `mira_ar_v2` recipe) | 0.83 | 0.67 | 0.56 | 0.44 | 0.17 | 9.7 / 5.1 / 2.5 / 0.84 | 0 / 0 / 0 |
| committed `mira_ar_experimental` | 0.78 | 0.67 | 0.56 | 0.39 | 0.28 | 7.1 / 5.0 / 2.4 / 1.0 (optimistic) | 2 / 1 / 1 |

No model fired on the three television fragments or outside the utterances of the held-out captures.
The two misses are in the television + wake-sound capture: its first «ميرا» (right after the wake
sound's tail) peaks at 0.23 and another at 0.32 under the television (the committed model: below 0.01
on both). The run
recommends **0.80** (0.56 false accepts/h, 95 % CI 0.21–1.22; 0.70 while music plays). Recall
counted over segments is 0.727 there, because the four television segments count as misses, so the
rule stops at the false-accept budget. Echo engine check: max |Δ| 3.2e-7. Model 591,440 bytes.
Times: 8.4 min (owner run), 5.7 min (synthetic-only). Outputs:
`~/.cache/mira-claude/wake/selftest/{out-owner,out-synthetic_only}/`, summary
`~/.cache/mira-claude/wake/selftest/selftest-report.json`.

This measures the pipeline and adaptation to a new "speaker". It does not measure the owner: the
stand-in is a transformed synthetic voice.

## 5. Installing on the Echo

**Through the desktop app (recommended, no restart).**

1. Put `<id>.tflite` and `<id>.json` in `~/.local/share/mira/wake-models/`. The app serves that
   directory to the Echo's address only, at `http://<pc>:18769/models/<id>.{json,tflite}` (`app.py`).
2. `MiraBridge.install_wake_model(id, phrase, ['ar'], model, [id])` offers the model over the ESPHome
   API as an external wake word (openwakeword, size, SHA-256, that URL). It then sets the active wake
   words: `[id]` alone now that Alexa is gone.
3. echod's `wake.Library.Ensure` fetches the manifest, then the model named in it. It refuses the
   model unless size and SHA-256 match, writes `<id>.tflite` and `<id>.json` into
   `/data/misc/echolocal/models/` through temporary files, reloads its model list and loads the
   selection. The offer's phrase and languages replace the manifest's.
4. Set `wake_threshold_1` (slot 1) to the recommended cutoff and read it back.

**By hand (serial console or SSH).** Copy both files into `/data/misc/echolocal/models/`. echod reads
that directory once, when it starts (`wake.Lib()` → `Reload`). It reads it again only after
downloading an offered model or purging unused ones. The API's configuration request does not rescan,
and selecting an id it has not listed is refused ("unknown wake word"). So restart the daemon (init
respawns it) or reboot, then select `[<id>]` through the API.

**Replacing a model under the same id.** The engine skips a slot that already holds that id
(`Engine.Use`). New weights under an old id are picked up only when the selection changes, when the
microphones are muted and unmuted, or when echod restarts. Select another word first and then the id
again, or give every training run its own id (`mira_ar_owner` vs `mira_ar_v2`).

Home Assistant keys its wake word picker by phrase, so two models that both say "Mira" collapse into
one entry there. The Mira app selects by id and is not affected.

## 6. Rolling back

Select the previous model through the API: `MiraBridge.select_wake_words(['mira_ar_experimental'])`
(the app's rollback, `FALLBACK_WAKE`). Put `wake_threshold_1` back to 0.60, the measured working value
for it. The newer model's files stay on the Echo unused. Delete `/data/misc/echolocal/models/<id>.tflite`
and `<id>.json` to remove them; echod's cache purge also deletes models no slot uses.
`mira_ar_experimental` and `hey_mira` are never overwritten.

## 7. Licensing

- **Background features** (`davidscripka/openwakeword_features`, the validation set and the ACAV100M
  sample): CC BY-NC-SA 4.0. Non-commercial, share-alike, attribution. A model trained with them is for
  the owner's personal use and is not cleared for commercial redistribution. The ACAV100M audio comes
  from YouTube videos collected for research.
- **Piper voices**: `ar_JO-kareem-medium` (dataset <https://github.com/AliMokhammad/arabicttstrain>,
  licence per that repository), `en_US-libritts_r-medium` (LibriTTS-R, CC BY 4.0) and
  `en_US-l2arctic-medium` (L2-ARCTIC, CC BY-NC 4.0). Model cards are in `<cache>/voices/`.
- **Gemini TTS** audio was generated with the owner's key on the free tier, under Google's Gemini API
  terms. It is used here only to train the owner's own wake word.
- **Whisper** (the base model Mira already ships, MIT) only checks synthetic pronunciations.
- **TECHO5** (MIT): the `oww`/`tflite`/`vec` packages are copied, not changed. The self-test uses
  TECHO5's `wake_word_triggered.pcm` (Home Assistant Voice PE sounds by Clayton Charles Tapp,
  CC BY 4.0) only to imitate the wake sound's tail.
- openWakeWord's front-end models (Apache 2.0) are embedded in TECHO5 unchanged.

## 8. Privacy

Owner captures are read in place and never copied into the repository. Derived clips live only in
memory, and their embeddings are cached in `<training dir>/featcache/`; delete it to remove every
derived trace. A run directory holds only the model, the manifest and reports (file names, times and
scores, no audio). Nothing is uploaded. Gemini received only fixed words and phrases, never owner audio.

## The first experimental model (history)

`mira_ar_experimental.tflite` was installed as a second model beside the owner-proven Alexa path
on 2026-09-28, and the owner confirmed Mira lit and replied. Device logs independently show two
`mira_ar_experimental` detections (peaks .729 and .911), followed by streamed replies of 6.28 s and
4.85 s with zero underruns. The actual detector cutoff in those logs is .60, not the requested .70.
It was trained on 400 synthetic clips from Piper ar_JO-kareem-medium (see "Why bare «ميرا» …").
A 15-second private owner recording, from the centre microphone and not the live Beamformer path,
was held out: old hey_mira peaked at 0.0023 and the experimental model at 0.9357, with other
utterances in it below threshold. That audio remains outside Git at `/data/mira/wake-calibration.raw`
on the Echo and `/tmp/mira-wake-calibration` locally. It was never uploaded and is not used by these
tools. Delete it when diagnostic work is complete.
