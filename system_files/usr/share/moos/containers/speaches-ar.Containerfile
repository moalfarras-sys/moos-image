# Arabic speech bootstrap image.
#
# Speaches 0.8.3 omits Piper's Arabic diacritization model, so Arabic TTS fails
# at runtime.  moos-prepare-speech-image obtains that model from Piper's pinned
# official release, verifies two SHA-256 values, and supplies it as this build
# context.  Pin the base manifest too: a moving image tag must never silently
# change the local speech stack.
FROM ghcr.io/speaches-ai/speaches@sha256:21e3df06d842fb7802ab470dd77c25f0e8c0d22950e8d8c6ae886e851af53ef8

# The upstream image leaves /home/ubuntu as 0750 root:root. The container runs
# as uid 1000 (ubuntu), so it cannot traverse to its own uvicorn executable and
# Podman reports the misleading `exec ... Permission denied`. Fix ownership of
# the application tree at image build time; do not weaken executable bits or
# run the speech server as root.
USER root
# The upstream image leaves /home/ubuntu as 0750 root:root. Make only the
# parent traversable and the application tree user-owned; the server remains
# non-root and no unrelated home data is exposed.
RUN chmod 0755 /home/ubuntu \
    && chown -R ubuntu:ubuntu /home/ubuntu/speaches
USER ubuntu

COPY --chown=ubuntu:ubuntu libtashkeel_model.ort \
    /home/ubuntu/speaches/.venv/lib/python3.12/site-packages/piper_phonemize/libtashkeel_model.ort

LABEL org.opencontainers.image.title="Speaches with Piper Arabic diacritization" \
      org.opencontainers.image.source="https://github.com/speaches-ai/speaches" \
      org.opencontainers.image.licenses="MIT"
