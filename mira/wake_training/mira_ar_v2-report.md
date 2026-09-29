# mira_ar_v2 — training report (2026-09-29T15:12:19)

Model `mira_ar_v2.tflite` (591456 bytes, sha256 `ab90400585b08fac…`), synthetic voices only, input 1x16x96, FC(96, RELU) → FC → LOGISTIC, float32. Python scoring vs echod engine: max |Δ| = 4.6e-07.


| cutoff | eval captures recall (new / baseline) | synthetic positives (new / baseline) | confusables fired (new / baseline) | background FA/h, 10.7 h (new) | FA/h last 2.1 h (new / baseline) |
| --- | --- | --- | --- | --- | --- |
| 0.50 | 0.8421 / 0.8553 | 0.8895 / 0.8 | 0.0358 / 0.179 | 9.723 | 7.946 / 3.74 |
| 0.55 | 0.7895 / 0.8421 | 0.8789 / 0.7947 | 0.0239 / 0.1623 | 7.479 | 7.012 / 3.272 |
| 0.60 | 0.7632 / 0.8158 | 0.8684 / 0.7737 | 0.0191 / 0.1551 | 5.142 | 5.142 / 2.805 |
| 0.65 | 0.75 / 0.8026 | 0.8316 / 0.7474 | 0.0143 / 0.1384 | 3.553 | 2.805 / 2.337 |
| 0.70 | 0.6842 / 0.7632 | 0.8 / 0.7263 | 0.0095 / 0.1313 | 2.524 | 2.805 / 0.935 |
| 0.75 | 0.6447 / 0.7368 | 0.7684 / 0.7105 | 0.0095 / 0.1122 | 1.496 | 1.87 / 0.935 |
| 0.80 | 0.5395 / 0.7105 | 0.7158 / 0.7 | 0.0048 / 0.0979 | 0.841 | 0.935 / 0.467 |
| 0.85 | 0.4737 / 0.6711 | 0.6789 / 0.6684 | 0.0 / 0.0764 | 0.28 | 0.467 / 0.467 |
| 0.90 | 0.2895 / 0.5395 | 0.5579 / 0.5947 | 0.0 / 0.0597 | 0.0 | 0.0 / 0.467 |
| 0.95 | 0.2105 / 0.3289 | 0.3684 / 0.5211 | 0.0 / 0.031 | 0.0 | 0.0 / 0.0 |

**Recommended cutoff: 0.65** — lowest cutoff whose background false accepts (3.553/h) are at or below those of mira_ar_experimental.tflite at its working cutoff 0.6 (4.955/h, same audio; that model trained on 80 % of it, so its figure is optimistic and this budget strict); no owner recordings yet, so there is no owner utterance to keep a margin under: tune it on the device from echod's near-miss log lines, or retrain with the owner's captures. While music plays echod uses 0.55.

## Synthetic holdout by voice family (rate at 0.5 / 0.6 / 0.7, new model)

- positive · ar_JO-kareem-medium: 0.8889 / 0.8611 / 0.7917 (144 clips, median peak 0.9198)
- positive · gemini: 0.8913 / 0.8913 / 0.8261 (46 clips, median peak 0.9302)
- confusable · ar_JO-kareem-medium: 0.0318 / 0.0091 / 0.0091 (220 clips, median peak 0.0347)
- confusable · en_US-l2arctic-medium: 0.0286 / 0.0286 / 0.0 (35 clips, median peak 0.0317)
- confusable · en_US-libritts_r-medium: 0.0427 / 0.0305 / 0.0122 (164 clips, median peak 0.0358)
- speech · ar_JO-kareem-medium: 0.0143 / 0.0143 / 0.0071 (140 clips, median peak 0.0099)
- speech · en_US-l2arctic-medium: 0.0076 / 0.0 / 0.0 (132 clips, median peak 0.0129)
- speech · en_US-libritts_r-medium: 0.0086 / 0.0057 / 0.0 (349 clips, median peak 0.009)

## Evaluation captures (peak score)

| file | start | end | new | baseline |
| --- | --- | --- | --- | --- |
| standin-00.wav | 1.09 | 1.69 | 0.845 | 0.9222 |
| standin-00.wav | 2.97 | 4.03 | 0.989 | 0.9851 |
| standin-00.wav | 5.77 | 6.82 | 0.956 | 0.9263 |
| standin-00.wav | 7.89 | 8.95 | 0.983 | 0.9792 |
| standin-00.wav | 10.23 | 10.76 | 0.683 | 0.5812 |
| standin-00.wav | 11.79 | 12.93 | 0.885 | 0.9886 |
| standin-01.wav | 0.48 | 1.69 | 0.992 | 0.9884 |
| standin-01.wav | 2.58 | 3.28 | 0.890 | 0.9721 |
| standin-01.wav | 4.86 | 5.64 | 0.899 | 0.9544 |
| standin-01.wav | 7.06 | 7.82 | 0.799 | 0.8678 |
| standin-01.wav | 8.70 | 9.36 | 0.889 | 0.9534 |
| standin-01.wav | 10.59 | 11.71 | 0.986 | 0.9874 |
| standin-02.wav | 0.87 | 1.60 | 0.868 | 0.8553 |
| standin-02.wav | 3.09 | 3.82 | 0.872 | 0.9694 |
| standin-02.wav | 5.04 | 5.69 | 0.710 | 0.7987 |
| standin-02.wav | 6.80 | 7.96 | 0.952 | 0.9243 |
| standin-02.wav | 8.91 | 9.58 | 0.352 | 0.8709 |
| standin-02.wav | 10.52 | 11.27 | 0.526 | 0.9432 |
| standin-03.wav | 1.10 | 1.89 | 0.684 | 0.7403 |
| standin-03.wav | 3.28 | 4.04 | 0.759 | 0.6107 |
| standin-03.wav | 5.37 | 6.12 | 0.648 | 0.9444 |
| standin-03.wav | 7.50 | 8.30 | 0.562 | 0.6562 |
| standin-03.wav | 9.33 | 10.55 | 0.888 | 0.7635 |
| standin-03.wav | 11.73 | 13.04 | 0.976 | 0.9716 |
| standin-04.wav | 0.72 | 1.63 | 0.791 | 0.6739 |
| standin-04.wav | 2.95 | 3.85 | 0.734 | 0.89 |
| standin-04.wav | 5.09 | 6.28 | 0.846 | 0.9193 |
| standin-04.wav | 7.26 | 8.48 | 0.968 | 0.9637 |
| standin-04.wav | 9.67 | 10.54 | 0.527 | 0.9212 |
| standin-04.wav | 11.65 | 12.95 | 0.952 | 0.9016 |
| standin-05.wav | 0.93 | 2.08 | 0.861 | 0.9719 |
| standin-05.wav | 3.22 | 3.88 | 0.537 | 0.8364 |
| standin-05.wav | 4.82 | 5.49 | 0.429 | 0.8608 |
| standin-05.wav | 6.31 | 7.37 | 0.654 | 0.9923 |
| standin-05.wav | 9.13 | 9.72 | 0.869 | 0.9601 |
| standin-05.wav | 10.81 | 11.47 | 0.794 | 0.9485 |
| standin-06.wav | 0.64 | 1.25 | 0.351 | 0.2817 |
| standin-06.wav | 2.04 | 2.79 | 0.783 | 0.935 |
| standin-06.wav | 3.85 | 4.53 | 0.454 | 0.4284 |
| standin-06.wav | 5.84 | 6.86 | 0.924 | 0.8837 |
| standin-06.wav | 7.58 | 8.37 | 0.926 | 0.9896 |
| standin-06.wav | 9.43 | 10.55 | 0.789 | 0.9701 |
| standin-07.wav | 0.49 | 1.57 | 0.799 | 0.9793 |
| standin-07.wav | 2.72 | 3.94 | 0.971 | 0.9851 |
| standin-07.wav | 4.71 | 5.36 | 0.920 | 0.853 |
| standin-07.wav | 6.05 | 7.07 | 0.971 | 0.9852 |
| standin-07.wav | 8.11 | 9.19 | 0.928 | 0.9349 |
| standin-07.wav | 10.16 | 11.18 | 0.971 | 0.9714 |
| standin-08.wav | 0.61 | 1.71 | 0.938 | 0.3731 |
| standin-08.wav | 2.98 | 3.72 | 0.270 | 0.8292 |
| standin-08.wav | 5.00 | 6.04 | 0.869 | 0.9207 |
| standin-08.wav | 7.25 | 8.57 | 0.895 | 0.9346 |
| standin-08.wav | 9.68 | 10.41 | 0.856 | 0.9691 |
| standin-08.wav | 11.45 | 12.51 | 0.966 | 0.8673 |
| standin-09.wav | 0.83 | 1.57 | 0.657 | 0.7231 |
| standin-09.wav | 2.34 | 3.47 | 0.955 | 0.6808 |
| standin-09.wav | 4.19 | 4.97 | 0.890 | 0.9596 |
| standin-09.wav | 6.53 | 7.67 | 0.962 | 0.9283 |
| standin-09.wav | 8.90 | 9.68 | 0.568 | 0.9466 |
| standin-09.wav | 10.95 | 11.69 | 0.674 | 0.9584 |
| standin-10.wav | 0.48 | 0.72 | 0.002 | 0.0 |
| standin-10.wav | 0.60 | 1.22 | 0.102 | 0.0042 |
| standin-10.wav | 1.29 | 1.75 | 0.049 | 0.0262 |
| standin-10.wav | 2.28 | 3.47 | 0.516 | 0.0512 |
| standin-10.wav | 3.83 | 4.88 | 0.117 | 0.0086 |
| standin-10.wav | 5.51 | 7.06 | 0.978 | 0.5103 |
| standin-10.wav | 8.08 | 9.39 | 0.866 | 0.5636 |
| standin-10.wav | 10.09 | 11.50 | 0.837 | 0.1371 |
| standin-10.wav | 12.28 | 12.93 | 0.082 | 0.0113 |
| standin-10.wav | 14.28 | 14.74 | 0.032 | 0.0192 |
| standin-11.wav | 0.93 | 2.09 | 0.720 | 0.8294 |
| standin-11.wav | 3.18 | 4.41 | 0.321 | 0.9742 |
| standin-11.wav | 5.10 | 5.88 | 0.840 | 0.9291 |
| standin-11.wav | 6.56 | 7.39 | 0.936 | 0.9739 |
| standin-11.wav | 8.48 | 9.26 | 0.842 | 0.8615 |
| standin-11.wav | 10.25 | 11.43 | 0.753 | 0.8972 |

## Captures

- standin-00.wav (eval, 15.0 s): 6 utterance(s)
- standin-01.wav (eval, 15.0 s): 6 utterance(s)
- standin-02.wav (eval, 15.0 s): 6 utterance(s)
- standin-03.wav (eval, 15.0 s): 6 utterance(s)
- standin-04.wav (eval, 15.0 s): 6 utterance(s)
- standin-05.wav (eval, 15.0 s): 6 utterance(s)
- standin-06.wav (eval, 15.0 s): 6 utterance(s)
- standin-07.wav (eval, 15.0 s): 6 utterance(s)
- standin-08.wav (eval, 15.0 s): 6 utterance(s)
- standin-09.wav (eval, 15.0 s): 6 utterance(s)
- standin-10.wav (eval, 15.0 s): 10 utterance(s)
- standin-11.wav (eval, 15.0 s): 6 utterance(s)

Timings (s): segmentation 0.1, synthetic_corpus 0.6, augmentation 118.9, front_end 0.7, training 208.1, evaluation 3.4, total 331.7
