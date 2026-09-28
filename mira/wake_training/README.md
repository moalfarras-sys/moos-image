# Experimental Arabic Mira wake model

Not a production-qualified wake word. Installed as a second model beside the
owner-proven Alexa path on 2026-09-28. The owner confirmed Mira lit and replied.
Device logs independently show two `mira_ar_experimental` detections (peaks .729
and .911), followed by streamed replies of 6.28s and 4.85s, both zero underruns.
The actual detector cutoff in those logs is .60, not the requested .70; preserve
the measured working configuration. Long-duration false-wake testing is pending.

Training uses 400 synthetic clips from Piper ar_JO-kareem-medium: 200 positive
variants of Mira / ya Mira / hi Mira, 200 negative/confusable phrases. No owner
audio is used in training. The script exports features with the TECHO5 Go front
end, fits a small 32-unit MLP and writes a float32 TFLite classifier (197720 bytes).
The 16x96 input and operators were exercised by TECHO5's real interpreter.

`training-report.json` describes window-level synthetic and background results,
not live recall or false activations per hour. Background validation is from
https://huggingface.co/datasets/davidscripka/openwakeword_features
(CC-BY-NC-SA-4.0); the experiment is not cleared for commercial redistribution.
Piper source: https://huggingface.co/rhasspy/piper-voices/tree/main/ar/ar_JO/kareem/medium
Review the individual voice model card before reuse. Copied Go feature exporter
is a task-specific helper for the existing TECHO5 source, not a firmware patch.

A 15-second private owner recording was held out. Its center microphone was
converted from S24 to S16 with 16x gain; this is NOT the live Beamformer path.
Old hey_mira peak: 0.0023; gain sweep 0.25–3: 0.0018–0.0025.
Experimental model peak: 0.9357. Some other utterances in the same recording
did not reach threshold; do not present the peak as overall recall.
Initial device trial uses threshold 0.70, streamed replies, 20s follow-up,
Beamformer mixing, active models `[alexa, mira_ar_experimental]`.

Raw/derived owner audio remains outside Git at `/data/mira/wake-calibration.raw`
on Echo and `/tmp/mira-wake-calibration` locally. It was never uploaded. Delete
when diagnostic work is complete. Do not commit recordings or transcripts.

Rollback: select `[alexa]` through the paired API; the working Alexa model and
old hey_mira model were not overwritten. Firmware remains unchanged.
