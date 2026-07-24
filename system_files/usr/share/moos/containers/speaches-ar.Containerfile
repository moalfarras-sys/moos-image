# Arabic speech bootstrap image.
#
# Speaches 0.8.3 omits Piper's Arabic diacritization model, so Arabic TTS fails
# at runtime.  moos-prepare-speech-image obtains that model from Piper's pinned
# official release, verifies two SHA-256 values, and supplies it as this build
# context.  Pin the base manifest too: a moving image tag must never silently
# change the local speech stack.
FROM ghcr.io/speaches-ai/speaches@sha256:21e3df06d842fb7802ab470dd77c25f0e8c0d22950e8d8c6ae886e851af53ef8

COPY --chown=ubuntu:ubuntu libtashkeel_model.ort \
    /home/ubuntu/speaches/.venv/lib/python3.12/site-packages/piper_phonemize/libtashkeel_model.ort

LABEL org.opencontainers.image.title="Speaches with Piper Arabic diacritization" \
      org.opencontainers.image.source="https://github.com/speaches-ai/speaches" \
      org.opencontainers.image.licenses="MIT"
